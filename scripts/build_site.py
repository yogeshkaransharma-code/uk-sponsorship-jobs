#!/usr/bin/env python3
"""Prepare a minimal, evidence-led static GitHub Pages site.

No paid services, API keys or Python packages are required. Only public-facing
HTML/CSS/JS and validated, recently observed job/sponsor records are published.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
DATA = ROOT / "data"


def valid_https_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.hostname)


def recent(day: object, days: int = 14) -> bool:
    try:
        checked = date.fromisoformat(str(day)[:10])
    except ValueError:
        return False
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=days) <= checked <= today


def build() -> dict:
    jobs_source = json.loads((DATA / "jobs.json").read_text(encoding="utf-8"))
    sponsor_source = json.loads((DATA / "sponsors.json").read_text(encoding="utf-8"))
    jobs = jobs_source.get("jobs", [])
    bulk_path = DATA / "bulk" / "jobs.json"
    if bulk_path.exists():
        bulk = json.loads(bulk_path.read_text(encoding="utf-8"))
        if not isinstance(bulk.get("jobs"), list):
            raise ValueError("Bulk import must contain a jobs list")
        jobs = list(jobs) + bulk["jobs"]
    companies = sponsor_source.get("companies", {})
    if not isinstance(jobs, list) or not isinstance(companies, dict):
        raise ValueError("Incorrect public data format")

    # Do not publish expired editorial examples, malformed links or stale feeds.
    selected = []
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or job.get("active") is not True:
            continue
        # Show every currently observed UK vacancy regardless of sponsorship policy.
        # The separate evidence fields are informational and can be filtered.
        if not recent(job.get("last_seen"), days=35 if str(job.get("id", "")).startswith("headcount-") else 14):
            continue
        link = job.get("apply_url")
        if not valid_https_url(link):
            continue
        # Identify Ashby duplicates with and without the /application suffix.
        canonical = link.rstrip("/").removesuffix("/application")
        if canonical in seen:
            continue
        seen.add(canonical)
        selected.append(job)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    for filename in ("index.html", "site.css", "site.js"):
        shutil.copy2(ROOT / filename, OUT / filename)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    # Minimize metadata on wire: omit boilerplate, personal data and full descriptions.
    # The employer's own job page remains the authoritative application source.
    selected = [{
        k: v for k, v in job.items()
        if k in (
            "id", "company", "legal_name", "title", "location", "category",
            "industry", "job_function", "experience_level", "salary",
            "sponsorship", "evidence", "evidence_source", "evidence_url",
            "apply_url", "verified_on", "posted_at", "last_seen", "active",
            "review", "summary", "source_attribution",
        )
    } for job in selected]
    public_jobs = {
        "updated_at": jobs_source.get("updated_at"),
        "mode": "automated",
        "coverage_note": "Vacancies collected from a limited set of public employer feeds. Not every UK job is indexed; a sponsor licence does not guarantee sponsorship.",
        "jobs": selected,
        "source_count": len(selected),
    }
    linked = {str(x) for job in selected for x in (job.get("company"), job.get("legal_name")) if x}
    public_sponsors = {
        "updated_at": sponsor_source.get("updated_at"),
        "official_register_url": sponsor_source.get("official_register_url"),
        "note": sponsor_source.get("note"),
        "companies": {k: v for k, v in companies.items() if k in linked},
    }
    for filename, content in (("jobs.json", public_jobs), ("sponsors.json", public_sponsors)):
        (OUT / "data" / filename).write_text(
            json.dumps(content, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
        )
    return {"published_jobs": len(selected), "published_sponsor_entries": len(public_sponsors["companies"])}


if __name__ == "__main__":
    print(json.dumps(build()))
