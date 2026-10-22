#!/usr/bin/env python3
"""Recover job descriptions from public employer ATS APIs, without Headcount credits.

The Headcount export has application links but no descriptions because we omitted
that field. This importer recovers original vacancy text from selected public
Greenhouse/Ashby/Lever job feeds. No scraping around logins or bypassing blocks.

It saves a compact enrichment overlay by canonical application URL. Each scheduled
run checks a bounded, rotating batch of employer boards and updates only records
successfully returned; other jobs are never falsely marked as having descriptions.
"""
from __future__ import annotations
import collections
import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"enriched"
BATCH=int(os.environ.get("ENRICH_BOARDS", "350"))
WORKERS=8
UA="SponsorHQ/0.5 (public job metadata; https://yogeshkaransharma-code.github.io/uk-sponsorship-jobs/)"
MAX_BYTES=15_000_000
MAX_DESC=7000

class CleanText(HTMLParser):
    """Convert an HTML job description to paragraph-preserving plain text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bits=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("br","p","h1","h2","h3","h4","li","ul","ol","section","div"):
            self.bits.append("\n")
        if tag=="li":self.bits.append("• ")
    def handle_endtag(self,tag):
        if tag in ("p","h1","h2","h3","h4","li","ul","ol","section","div"):
            self.bits.append("\n")
    def handle_data(self,data):self.bits.append(data)
    def get(self):return "".join(self.bits)

def plain(raw):
    if not isinstance(raw,str) or not raw.strip():return ""
    parser=CleanText()
    try:
        parser.feed(raw[:120000])
        body=parser.get()
    except Exception:
        body=raw
    body=html.unescape(body)
    lines=[re.sub(r"[ \t]+"," ",l).strip() for l in body.splitlines()]
    filtered=[]
    for line in lines:
        if line and (not filtered or filtered[-1]!=line):filtered.append(line)
    text="\n".join(filtered)
    if len(text)>MAX_DESC:
        text=text[:MAX_DESC].rsplit(" ",1)[0].strip()+"…"
    return text

def canonical(url):
    p=urlsplit(url or "")
    if p.scheme!="https":return ""
    return (p.netloc.lower()+p.path).rstrip("/").removesuffix("/application").lower()

def identify(url):
    """Only exact public ATS hostnames. Never use untrusted link as a fetch URL."""
    p=urlsplit(url or "")
    if p.scheme!="https":return None
    h=p.hostname.lower() if p.hostname else ""
    paths=[x for x in p.path.split("/") if x]
    if h in ("job-boards.greenhouse.io","job-boards.eu.greenhouse.io","boards.greenhouse.io"):
        if len(paths)>=3 and paths[1]=="jobs" and paths[2].isdigit():
            return ("greenhouse",paths[0],paths[2])
    if h=="boards.greenhouse.io" and p.path=="/embed/job_app":
        args=parse_qs(p.query)
        slug=(args.get("for") or [""])[0];job=(args.get("token") or [""])[0]
        if job.isdigit():return ("greenhouse",slug,job)
    if h=="jobs.ashbyhq.com" and len(paths)>=2:
        return ("ashby",paths[0],paths[1].lower())
    if h in ("jobs.lever.co","jobs.eu.lever.co") and len(paths)>=2:
        return ("lever",paths[0],paths[1].lower())
    return None

TOKEN=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,105}$")

def get_json(url):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urlopen(req,timeout=25) as response:
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:raise ValueError("Public employer feed too large")
    return json.loads(body)

def source_jobs(provider,token):
    part=quote(token,safe="._-")
    if provider=="greenhouse":
        return get_json("https://boards-api.greenhouse.io/v1/boards/"+part+"/jobs?content=true").get("jobs",[])
    if provider=="ashby":
        return get_json("https://api.ashbyhq.com/posting-api/job-board/"+part+"?includeCompensation=true").get("jobs",[])
    if provider=="lever":
        try:
            return get_json("https://api.lever.co/v0/postings/"+part+"?mode=json")
        except (HTTPError,URLError,TimeoutError):
            return get_json("https://api.eu.lever.co/v0/postings/"+part+"?mode=json")
    return []

def record_details(provider,job):
    if provider=="greenhouse":
        ident=str(job.get("id") or "")
        body=plain(job.get("content") or "")
        link=job.get("absolute_url")
    elif provider=="ashby":
        ident=str(job.get("id") or job.get("jobId") or "").lower()
        body=plain(job.get("descriptionPlain") or job.get("descriptionHtml") or "")
        link=job.get("jobUrl") or job.get("applyUrl")
    else:
        ident=str(job.get("id") or "").lower()
        body=plain(job.get("descriptionPlain") or job.get("description") or "")
        extra=job.get("lists") or []
        if isinstance(extra,list):
            for block in extra:
                if isinstance(block,dict):
                    body+="\n"+plain(block.get("text") or block.get("content") or "")
        link=job.get("hostedUrl") or job.get("applyUrl")
    return ident,body.strip(),link

def source_board(source):
    provider,token,targets=source
    try:
        fetched=source_jobs(provider,token)
        if not isinstance(fetched,list):raise ValueError("API body is not a job list")
        matched={}
        count=0
        by_ident=collections.defaultdict(list)
        for canon,jobid in targets:by_ident[jobid].append(canon)
        for rec in fetched[:3000]:
            if not isinstance(rec,dict):continue
            ident,description,source_link=record_details(provider,rec)
            if len(description)<100:continue
            candidates=list(by_ident.get(ident,[]))
            if source_link:
                source_canon=canonical(source_link)
                if source_canon and source_canon in {u for u,_ in targets}:
                    candidates.append(source_canon)
            for canon in candidates:
                if not canon:continue
                # Don't claim visa sponsorship from keyword inference.
                # Preserve original short evidence and show original wording for review.
                matched[canon]={"description_excerpt":description,
                                "description_source":"Public employer "+provider+" API",
                                "description_checked_at":datetime.now(timezone.utc).date().isoformat()}
            count+=1
        return provider,token,len(fetched),matched,""
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError) as exc:
        return provider,token,0,{},type(exc).__name__+": "+str(exc)[:80]

def load_targets():
    targets=collections.defaultdict(dict)
    num=0
    allfiles=sorted((DATA/"bulk").glob("headcount-*.json"))
    if not allfiles:raise RuntimeError("No Headcount bulk files")
    for path in allfiles:
        rows=json.loads(path.read_text(encoding="utf-8")).get("jobs",[])
        for row in rows:
            num+=1
            url=row.get("apply_url") or ""
            parsed=identify(url)
            if not parsed:continue
            provider,token,jobid=parsed
            if not TOKEN.fullmatch(token):continue
            canon=canonical(url)
            if canon:targets[(provider,token)][canon]=jobid
    return num,targets

def main():
    total,targets=load_targets()
    ranked=sorted(targets.items(),key=lambda x:(-len(x[1]),x[0]))
    if not ranked:raise RuntimeError("No ATS job URLs found")
    n=max(1,(len(ranked)+BATCH-1)//BATCH)
    batch=0 if "--first" in sys.argv else datetime.now(timezone.utc).date().toordinal()%n
    if "--batch" in sys.argv:
        idx=sys.argv.index("--batch")
        batch=int(sys.argv[idx+1])%n
    selected=ranked[batch*BATCH:(batch+1)*BATCH]
    print("Headcount records: {}; publicly fetchable ATS boards: {}; distinct target jobs: {}; batch {}/{} ({} boards, {} target jobs)".format(total,len(ranked),sum(len(v) for _,v in ranked),batch+1,n,len(selected),sum(len(v) for _,v in selected)),flush=True)
    success=0
    items={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures=[pool.submit(source_board,(key[0],key[1],list(target.items()))) for key,target in selected]
        for future in concurrent.futures.as_completed(futures):
            provider,token,fetched,matching,error=future.result()
            if not error:success+=1
            items.update(matching)
    print("Employer boards fetched successfully: {}/{}; job descriptions recovered: {}".format(success,len(selected),len(items)),flush=True)
    if success<max(5,len(selected)//5):raise RuntimeError("Too many source errors; preserving existing descriptions")
    # Zero matches may legitimately happen if providers rotate job IDs; do not
    # replace earlier nonempty data with an empty list.
    if not items:raise RuntimeError("No descriptions returned")
    OUT.mkdir(exist_ok=True,parents=True)
    out=OUT/("ats-%02d.json"%batch)
    out.write_text(json.dumps({"source":"Public employer ATS career feeds",
       "updated_at":datetime.now(timezone.utc).date().isoformat(),
       "records":items},ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Saved {} descriptions to {}".format(len(items),out.name),flush=True)

if __name__=="__main__":
    main()
