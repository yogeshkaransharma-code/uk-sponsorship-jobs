#!/usr/bin/env python3
"""Print counts of employer ATS origins in the existing bulk metadata."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
hosts=Counter()
examples={}
for path in sorted((ROOT/"data"/"bulk").glob("headcount-*.json")):
    rows=json.loads(path.read_text(encoding="utf-8")).get("jobs",[])
    for j in rows:
        u=j.get("apply_url") or ""
        host=(urlsplit(u).hostname or "").lower()
        if not host:continue
        if "myworkdayjobs.com" in host:
            category="*.myworkdayjobs.com"
        elif host.endswith(".workable.com"):category="*.workable.com"
        elif host.endswith(".recruitee.com"):category="*.recruitee.com"
        elif host.endswith(".personio.de") or host.endswith(".personio.com"):category="*.personio"
        else:category=host
        hosts[category]+=1
        examples.setdefault(category,u[:180])
print("TOP HOSTS (number of UK jobs, real example link)",flush=True)
for category,count in hosts.most_common(60):
    print("{:6d}  {:40s} {}".format(count,category,examples[category]),flush=True)
print("TOTAL HOSTED URLS",sum(hosts.values()),flush=True)
