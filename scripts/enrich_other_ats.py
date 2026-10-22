#!/usr/bin/env python3
"""Enrich UK vacancies from public SmartRecruiters and Workday job-detail APIs.

Bounded rotating batches, safe hostname rules, no login, no Headcount usage.
Respect errors and 429 rate limiting; failed jobs remain in the catalogue with
sponsorship unconfirmed, never fabricated.
"""
from __future__ import annotations
from collections import Counter
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from enrich_descriptions import plain, canonical

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
PER_VENDOR=int(os.getenv("DETAILS_PER_VENDOR","650"))
WORKERS=10
UA="SponsorHQ/0.5 (job descriptions from public career APIs; https://yogeshkaransharma-code.github.io/uk-sponsorship-jobs/)"
TOKEN=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,90}$")
HOST=re.compile(r"^[a-z0-9-]+\.wd[0-9]+\.myworkdayjobs\.com$")
LOCK=threading.Lock()
LAST={}

def parse_target(link):
    p=urlsplit(link or "")
    if p.scheme!="https" or not p.hostname:return None
    host=p.hostname.lower()
    sections=[x for x in p.path.split("/") if x]
    if host=="jobs.smartrecruiters.com" and len(sections)>=2 and TOKEN.fullmatch(sections[0]):
        posting=sections[1].split("-")[0]
        if re.fullmatch(r"[0-9]{6,20}",posting):
            return ("smart",sections[0],posting,host,canonical(link))
    if HOST.fullmatch(host):
        if sections and re.fullmatch(r"[a-z]{2}-[A-Z]{2}",sections[0]):sections=sections[1:]
        if len(sections)>=3 and sections[1]=="job" and TOKEN.fullmatch(sections[0]):
            tenant=host.split(".")[0]
            detail="/".join(sections[1:])
            return ("workday",tenant,sections[0],host,canonical(link),detail)
    return None

def json_get(url,rate_host):
    # Bound repeated requests to any single employer. Mixed employers are concurrent.
    with LOCK:
        last=LAST.get(rate_host,0.)
        now=time.monotonic()
        when=max(now,last+0.8)
        LAST[rate_host]=when
    pause=when-time.monotonic()
    if pause>0:time.sleep(pause)
    req=Request(url,headers={"Accept":"application/json","User-Agent":UA})
    with urlopen(req,timeout=22) as resp:
        data=resp.read(2_000_000)
    return json.loads(data)

def fetch_one(target):
    kind=target[0]
    key=target[4]
    try:
        if kind=="smart":
            _,company,post,host,_=target
            url="https://api.smartrecruiters.com/v1/companies/"+quote(company,safe="._-")+"/postings/"+post
            record=json_get(url,company.lower()+".smartrecruiters")
            if record.get("active") is False:return kind,key,"closed",None
            ad=record.get("jobAd") or {}
            sec=ad.get("sections") or ad
            fragments=[]
            for label in ("jobDescription","qualifications","additionalInformation"):
                x=sec.get(label)
                part=x.get("text") if isinstance(x,dict) else x
                if isinstance(part,str) and part.strip():
                    fragments.append(label.replace("jobDescription","About this job").replace("additionalInformation","Additional information").title()+"\n"+plain(part))
            text="\n\n".join(fragments)
        else:
            _,tenant,site,host,_,external=target
            url="https://"+host+"/wday/cxs/"+quote(tenant,safe="")+"/"+quote(site,safe="")+"/"+external
            record=json_get(url,host)
            info=record.get("jobPostingInfo") or {}
            text=plain(info.get("jobDescription") or "")
        if len(text)<100:return kind,key,"missing",None
        from refresh import classify
        sponsorship,evidence=classify(text[:15000])
        overlay={
            "description_excerpt":text[:7000],
            "description_source":("Public SmartRecruiters" if kind=="smart" else "Public Workday")+" job-detail API",
            "description_checked_at":datetime.now(timezone.utc).date().isoformat(),
        }
        if sponsorship in ("stated","conditional","unavailable") and evidence:
            overlay.update({
                "sponsorship":sponsorship,
                "evidence":evidence,
                "evidence_source":"Automatically detected wording in original employer job advert",
            })
        return kind,key,"ok",overlay
    except HTTPError as exc:
        return kind,key,"rate_limited" if exc.code==429 else "HTTP_"+str(exc.code),None
    except (URLError,TimeoutError,OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
        return kind,key,"error",None

def targets():
    all_rows=[]
    for path in sorted((DATA/"bulk").glob("headcount-*.json")):
        rows=json.loads(path.read_text(encoding="utf-8")).get("jobs",[])
        for row in rows:
            t=parse_target(row.get("apply_url") or "")
            if t:all_rows.append(t)
    # Stable deterministic ordering distributes tenants evenly across batches.
    by_kind={}
    for kind in ("smart","workday"):
        subset=[x for x in all_rows if x[0]==kind]
        subset.sort(key=lambda x:hashlib.sha256(x[4].encode("utf-8")).hexdigest())
        # Deduplicate canonical URL.
        unique={x[4]:x for x in subset}
        by_kind[kind]=list(unique.values())
    return by_kind

def main():
    catalog=targets()
    longest=max((len(v)+PER_VENDOR-1)//PER_VENDOR for v in catalog.values())
    index=0 if "--first" in sys.argv else datetime.now(timezone.utc).date().toordinal()%longest
    if "--batch" in sys.argv:
        index=int(sys.argv[sys.argv.index("--batch")+1])%longest
    requested=[]
    for name,items in catalog.items():
        print(name,"candidate jobs:",len(items),flush=True)
        requested.extend(items[index*PER_VENDOR:(index+1)*PER_VENDOR])
    print("Batch {}/{}: querying {} individual public job descriptions".format(index+1,longest,len(requested)),flush=True)
    if not requested:raise RuntimeError("No jobs selected for batch")
    enriched={}
    statuses=Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for kind,key,status,item in pool.map(fetch_one,requested):
            statuses[kind+"_"+status]+=1
            if item:enriched[key]=item
    print("Job detail outcomes:",dict(statuses),"successful descriptions:",len(enriched),flush=True)
    if not enriched:raise RuntimeError("No descriptions were returned; preserving prior jobs")
    output=DATA/"enriched"
    output.mkdir(parents=True,exist_ok=True)
    filename="ats-details-%02d.json"%index
    (output/filename).write_text(json.dumps({
        "source":"Public SmartRecruiters and Workday job detail APIs",
        "updated_at":datetime.now(timezone.utc).date().isoformat(),
        "records":enriched,
    },ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Saved",len(enriched),"descriptions in",filename,flush=True)

if __name__=="__main__":
    main()
