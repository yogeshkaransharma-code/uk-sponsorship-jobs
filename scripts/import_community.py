#!/usr/bin/env python3
"""Import recent UK jobs from a free MIT-licensed public GitHub job snapshot.

No credentials, payment, or user interaction. Metadata only, original apply links.
Source: https://github.com/ConorsCode/open-jobs-data
MIT copyright (c) 2026 open-jobs-data contributors.
Job adverts themselves remain the respective employers' property.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/ConorsCode/open-jobs-data/main/data/"
MAX_BYTES = 80_000_000
UK = re.compile(
    r"\b(united kingdom|great britain|uk|england|scotland|wales|northern ireland|"
    r"london|manchester|leeds|birmingham|bristol|glasgow|edinburgh|cardiff|belfast|"
    r"liverpool|sheffield|nottingham|oxford|cambridge|reading|newcastle|brighton|"
    r"leicester|coventry|southampton|portsmouth|york|aberdeen|dundee|"
    r"guildford|milton keynes|swansea|chester|preston|luton|"
    r"canterbury|norwich|slough|bath|exeter|maidstone|sunderland|"
    r"wolverhampton|swindon|bolton|ipswich|plymouth|derby|"
    r"west midlands|east midlands|surrey|kent|essex|yorkshire|"
    r"hampshire|lancashire|berkshire|buckinghamshire|hertfordshire)\b", re.I)
EXCLUDE = re.compile(
    r"\b(new york|usa|united states|canada|australia|india|germany|france|"
    r"netherlands|ireland\b(?![\s,]*(?:northern))|cambridge,\s*ma|"
    r"manchester,\s*nh|london,\s*on|birmingham,\s*al)\b", re.I)


def fetch_json(name):
    if name not in ("summary.json", "jobs.json"):
        raise ValueError("Unexpected source")
    req = Request(BASE + name, headers={"User-Agent": "SponsorHQ-public-index/0.2"})
    with urlopen(req, timeout=70) as resp:
        size = resp.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Oversized dataset")
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Unexpected dataset size")
    return json.loads(raw)


def is_uk_location(locations):
    if not isinstance(locations, list):
        locations = [locations]
    for item in locations:
        if not isinstance(item, str):
            continue
        if EXCLUDE.search(item):
            continue
        if UK.search(item):
            return True
    return False


def make_record(row, snapshot_day):
    if not isinstance(row, dict) or not is_uk_location(row.get("locations") or []):
        return None
    company, title, url = row.get("company"), row.get("title"), row.get("applyUrl")
    if not all(isinstance(v, str) and v.strip() for v in (company, title, url)):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    locs = row.get("locations")
    loc = next((x for x in locs if isinstance(x, str) and not EXCLUDE.search(x) and UK.search(x)), "United Kingdom")
    ident = hashlib.sha256(url.split("?")[0].rstrip("/").encode("utf-8")).hexdigest()[:18]
    return {
        "id": "open-data-" + ident,
        "company": company.strip()[:200],
        "legal_name": "",
        "title": title.strip()[:240],
        "location": loc[:180],
        "category": "Industry not verified",
        "industry": "Other / unclassified",
        "job_function": "Not classified",
        "experience_level": "Not specified",
        "salary": "Not disclosed",
        "sponsorship": "unknown",
        "evidence": "No visa sponsorship statement checked in this public data feed.",
        "evidence_source": "Public third-party job index; employer advert not reviewed for sponsorship",
        "evidence_url": url,
        "apply_url": url,
        "verified_on": snapshot_day,
        "posted_at": str(row.get("postedAt") or "")[:10],
        "last_seen": snapshot_day,
        "active": True,
        "review": "auto",
        "summary": "UK vacancy in a public employer-feed index. Sponsorship not independently assessed.",
        "source_attribution": "ConorsCode/open-jobs-data (MIT)",
    }


def main():
    summary = fetch_json("summary.json")
    snapshot = datetime.fromisoformat(summary["generatedAt"].replace("Z", "+00:00")).date()
    age = (datetime.now(timezone.utc).date() - snapshot).days
    if not 0 <= age <= 14:
        raise ValueError("Source snapshot is too old or future-dated: " + str(snapshot))
    rows = fetch_json("jobs.json")
    if not isinstance(rows, list) or len(rows) < 5000:
        raise ValueError("Unexpected source jobs list")
    matches = {}
    for row in rows:
        job = make_record(row, snapshot.isoformat())
        if job:
            matches[job["apply_url"].split("?")[0].rstrip("/")] = job
    if len(matches) < 10:
        raise RuntimeError("Not enough UK vacancies found. Refusing to replace existing data")
    output = ROOT / "data" / "bulk"
    output.mkdir(exist_ok=True, parents=True)
    jobs = list(matches.values())
    (output / "community.json").write_text(json.dumps({
        "updated_at": snapshot.isoformat(),
        "source": "https://github.com/ConorsCode/open-jobs-data",
        "licence": "MIT; 2026 open-jobs-data contributors",
        "jobs": jobs,
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Source rows: {}; identified UK roles: {}; snapshot: {}".format(len(rows), len(jobs), snapshot), flush=True)


if __name__ == "__main__":
    sys.exit(main())
