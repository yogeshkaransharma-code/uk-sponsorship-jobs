#!/usr/bin/env python3
"""Fetch UK vacancies directly from employer public job-board APIs.

Source of board identifiers: a free directory of *live board addresses*:
https://kalebconfer-sys.github.io/job-board-directory/
Only Greenhouse, Ashby and Lever GET APIs; no logins or paid data.
Runs one rotating batch per day and leaves other batches intact.
Avoid copying full descriptions; link to the original application.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"bulk"
DIRECTORY="https://kalebconfer-sys.github.io/job-board-directory/job-board-directory.json"
UA="SponsorHQ/0.4 (+https://yogeshkaransharma-code.github.io/uk-sponsorship-jobs/; job discovery, low-rate)"
BATCH_SIZE=500
MAX_RESPONSE=18_000_000
UK=re.compile(r"\b(united kingdom|great britain|uk|england|scotland|wales|northern ireland|"
    r"london|manchester|birmingham|leeds|sheffield|bristol|glasgow|edinburgh|"
    r"cardiff|belfast|liverpool|newcastle|oxford|cambridge|nottingham|"
    r"brighton|reading|coventry|leicester|southampton|portsmouth|york|"
    r"aberdeen|dundee|norwich|guildford|milton keynes|watford|swansea|"
    r"bath|chester|bolton|preston|slough|luton|exeter|derby|sunderland|"
    r"hampshire|kent|surrey|essex|lancashire|yorkshire|west midlands)\b",re.I)
OTHER=re.compile(r"\b(usa|united states|canada|australia|new york|boston|"
    r"cambridge,\s*ma|manchester,\s*nh|london,\s*on|birmingham,\s*al|india|"
    r"germany|singapore|france|ireland,\s*(?!northern))\b",re.I)
TOKEN=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,110}$")


def json_get(url, limit=MAX_RESPONSE):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urlopen(req,timeout=22) as resp:
        raw=resp.read(limit+1)
    if len(raw)>limit: raise ValueError("Response too large")
    return json.loads(raw)


def safe_url(url):
    if not isinstance(url,str) or len(url)>1200:return False
    x=urlparse(url)
    return x.scheme=="https" and bool(x.netloc) and not x.username and not x.password


def name_text(v):
    if isinstance(v,dict):return str(v.get("name") or v.get("location") or "")
    return str(v or "")


def loc_ok(location,country=""):
    country=str(country or "").strip().lower()
    if country and country not in ("gb","gbr","uk","united kingdom","great britain","england","scotland","wales","northern ireland"):
        return False
    if country:return True
    return bool(UK.search(location)) and not (bool(OTHER.search(location)) and not bool(re.search(r"\b(united kingdom|england|scotland|wales|uk)\b",location,re.I)))


def source_records(board):
    provider,token=board["platform"],board["token"]
    if not TOKEN.fullmatch(token):return []
    slug=quote(token,safe="._-")
    if provider=="greenhouse":
        body=json_get("https://boards-api.greenhouse.io/v1/boards/"+slug+"/jobs?content=true")
        return body.get("jobs",[])[:3000]
    if provider=="ashby":
        body=json_get("https://api.ashbyhq.com/posting-api/job-board/"+slug+"?includeCompensation=true")
        return [j for j in body.get("jobs",[]) if j.get("isListed") is not False][:3000]
    if provider=="lever":
        return json_get("https://api.lever.co/v0/postings/"+slug+"?mode=json")[:3000]
    return []


def adapt(board,raw,stamp):
    if not isinstance(raw,dict):return None
    provider=board["platform"]
    if provider=="greenhouse":
        title=raw.get("title") or ""
        location=name_text(raw.get("location"))
        country=""
        url=raw.get("absolute_url")
        desc=raw.get("content") or ""
        posted=raw.get("first_published") or ""
    elif provider=="ashby":
        title=raw.get("title") or ""
        location=name_text(raw.get("location"))
        country=""
        url=raw.get("applyUrl") or raw.get("jobUrl")
        desc=raw.get("descriptionPlain") or ""
        posted=raw.get("publishedAt") or ""
    elif provider=="lever":
        title=raw.get("text") or ""
        cats=raw.get("categories") or {}
        locs=cats.get("allLocations") or [cats.get("location") or ""]
        location=" / ".join(str(x) for x in locs if x)
        country=raw.get("country") or ""
        url=raw.get("applyUrl") or raw.get("hostedUrl")
        desc=raw.get("descriptionPlain") or ""
        posted=""
    else:return None
    if not isinstance(title,str) or not title.strip() or not safe_url(url):
        return None
    if not loc_ok(location,country):return None
    # Avoid connecting to an arbitrary source-provided URL during collection.
    # Source URLs are outgoing application links only.
    from refresh import classify, job_function, experience_level, as_text
    clean_description=as_text(desc)
    status,evidence=classify(clean_description[:15000])
    excerpt=clean_description[:900].rstrip()
    if len(clean_description)>900 and ' ' in excerpt:
        excerpt=excerpt.rsplit(' ',1)[0]+'…'
    canonical=url.split("#")[0].split("?")[0].rstrip("/").removesuffix("/application")
    uid=hashlib.sha256(canonical.encode()).hexdigest()[:20]
    return {
       "id":"direct-"+uid,"company":str(board["company"])[:150],
       "legal_name":"","title":title.strip()[:220],
       "location":location[:160] or "United Kingdom",
       "category":"Industry not yet classified","industry":"Other / unclassified",
       "job_function":job_function(title),"experience_level":experience_level(title),
       "salary":"Not disclosed","sponsorship":status,"description_excerpt":excerpt,
       "evidence":evidence,"evidence_source":"Public employer careers API; automated text detection",
       "evidence_url":url,"apply_url":url,"verified_on":stamp,
       "posted_at":str(posted)[:10],"last_seen":stamp,"active":True,
       "review":"auto","summary":"UK vacancy from the employer's public careers feed. Check eligibility and visa policy.",
       "source_attribution":"Employer careers feed, board discovered via job-board-directory",
    }


def selected_boards(directory,existing):
    if not isinstance(directory,list):raise ValueError("Directory format changed")
    valid=[]
    seen=set()
    for board in directory:
        if not isinstance(board,dict):continue
        platform,token=board.get("platform"),board.get("token")
        if platform not in ("greenhouse","ashby","lever") or not isinstance(token,str) or not TOKEN.fullmatch(token):
            continue
        if (platform,token) in seen or (platform,token) in existing:continue
        seen.add((platform,token))
        n=board.get("open_roles") or 0
        if not isinstance(n,int) or n<1:continue
        valid.append({"platform":platform,"token":token,"company":str(board.get("company") or token),"open_roles":n})
    # Distribute large boards across the rotation instead of overloading one run.
    valid.sort(key=lambda b:(-min(b["open_roles"],500),b["platform"],b["token"]))
    return valid


def collect_one(board,stamp):
    try:
        source=source_records(board)
        jobs={}
        for raw in source:
            row=adapt(board,raw,stamp)
            if row:jobs[row["apply_url"]]=row
        return board,len(source),list(jobs.values()),""
    except (ValueError,TypeError,KeyError,HTTPError,URLError,TimeoutError,OSError) as e:
        return board,0,[],str(e)[:100]


def run():
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from refresh import read
    existing={(s["provider"],s["board"]) for s in read("sources.json") if s.get("enabled") and s["provider"] in ("greenhouse","ashby","lever")}
    directory=json_get(DIRECTORY,8_000_000)
    boards=selected_boards(directory,existing)
    if len(boards)<500:raise ValueError("Directory has too few valid boards")
    batches=(len(boards)+BATCH_SIZE-1)//BATCH_SIZE
    # UTC date cycle: one batch each day, 13 days for approx 6k boards.
    batch=(datetime.now(timezone.utc).date().toordinal())%batches
    if "--first" in sys.argv:batch=0
    current=boards[batch*BATCH_SIZE:(batch+1)*BATCH_SIZE]
    if not current:raise RuntimeError("No boards to check")
    print("Verified board directory: {} usable boards; batch {} of {}, checking {} boards".format(len(boards),batch+1,batches,len(current)),flush=True)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(collect_one,b,stamp) for b in current]
        for result in concurrent.futures.as_completed(futures):
            results.append(result.result())
    successes=sum(1 for r in results if not r[3])
    indexed={}
    for _,_,jobs,_ in results:
        for row in jobs:indexed[row["apply_url"].split("?")[0].rstrip("/")]=row
    print("Board API responses: {}/{} successful; UK jobs: {}; failed: {}".format(successes,len(current),len(indexed),len(current)-successes),flush=True)
    if successes<max(20,len(current)//6):
        raise RuntimeError("Too many employer API failures; not changing existing data")
    if len(indexed)<10:
        raise RuntimeError("Very few UK jobs returned; preserving previous data")
    OUT.mkdir(exist_ok=True,parents=True)
    target=OUT/("boards-%02d.json"%batch)
    target.write_text(json.dumps({"updated_at":stamp,"directory":DIRECTORY,"jobs":list(indexed.values())},separators=(",",":"),ensure_ascii=False)+"\n",encoding="utf-8")
    print("Prepared {} UK vacancies from direct employer feeds in {}".format(len(indexed),target.name),flush=True)


if __name__=="__main__":
    run()
