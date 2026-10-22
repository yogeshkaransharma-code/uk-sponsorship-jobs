#!/usr/bin/env python3
"""Flag possible UK sponsor-register name matches across the entire job board.

A name match is NOT a verified employer legal-entity link and is not evidence
that a vacancy sponsors. Only the 19 manually curated entities can be 'verified'.
"""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
import re
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
CORPORATE=r"(?:ltd|limited|plc|llp|inc|incorporated|corporation|corp|co|company)"
def normalized(name):
    if not isinstance(name,str):return ""
    s=name.casefold().replace("&"," and ")
    s=re.sub(r"[^a-z0-9]+"," ",s).strip()
    s=re.sub(r"^the ","",s)
    return s
def stem(name):
    s=normalized(name)
    while True:
        new=re.sub(r"\s+"+CORPORATE+r"$","",s).strip()
        if new==s:return s
        s=new

def get_candidates(names,registered):
    exact=defaultdict(set)
    roots=defaultdict(set)
    for legal,rows in registered.items():
        if not any("skilled worker" in str(r.get("route","")).casefold() for r in rows):
            continue
        # Preserve each distinct legal string in ambiguity checks.
        legal_name=str(rows[0].get("name") or legal).strip()
        exact[normalized(legal_name)].add(legal_name)
        roots[stem(legal_name)].add(legal_name)
    found={}
    for name in sorted(names):
        norm=normalized(name)
        root=stem(name)
        matches=exact.get(norm,set())
        match_type="Exact register-name match"
        if not matches and (len(root)>=7 or (len(root)>=4 and normalized(name)!=root)) and root not in {
            "services","solutions","consulting","trading","holdings","group",
            "partners","technology","technologies","healthcare","management",
            "recruitment","energy","digital","international","education",
        }:
            matches=roots.get(root,set())
            match_type="Similar register name (corporate suffix ignored)"
        # Avoid silently assigning one employer's identity where many exist.
        if len(matches)!=1:continue
        legal=next(iter(matches))
        found[name]={
            "status":"name_match",
            "register_name":legal,
            "route":"Skilled Worker",
            "match_basis":match_type,
            "checked_on":datetime.now(timezone.utc).date().isoformat(),
            "note":"Possible sponsor-register name match only. Legal employer identity and job-level sponsorship not confirmed.",
        }
    return found

def main():
    from refresh import official_register
    companies=set()
    for path in [DATA/"jobs.json",DATA/"bulk"/"community.json"]+sorted((DATA/"bulk").glob("headcount-*.json"))+sorted((DATA/"bulk").glob("boards-*.json")):
        if not path.exists():continue
        rows=json.loads(path.read_text(encoding="utf-8")).get("jobs",[])
        for row in rows:
            if isinstance(row,dict) and row.get("company"):
                companies.add(str(row["company"]).strip())
    print("Checking sponsor-register names for {} job-board employer labels".format(len(companies)),flush=True)
    names,url,n=official_register()
    matched=get_candidates(companies,names)
    out=DATA/"register_candidates.json"
    out.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),
        "source":url,
        "candidate_count":len(matched),
        "candidates":matched},ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Source register rows: {}; plausible names (NOT verified licences): {}".format(n,len(matched)),flush=True)

if __name__=="__main__":
    main()
