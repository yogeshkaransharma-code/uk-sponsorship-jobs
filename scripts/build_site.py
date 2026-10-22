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
    bulk_files = [DATA / "bulk" / "community.json"] + sorted((DATA / "bulk").glob("boards-*.json"))
    headcount_files = sorted((DATA / "bulk").glob("headcount-*.json"))
    bulk_files += headcount_files if headcount_files else [DATA / "bulk" / "jobs.json"]
    for bulk_path in bulk_files:
        if bulk_path.exists():
            bulk = json.loads(bulk_path.read_text(encoding="utf-8"))
            if not isinstance(bulk.get("jobs"), list):
                raise ValueError("Bulk import must contain a jobs list")
            jobs = list(jobs) + bulk["jobs"]
    # Join recovered descriptions against canonical job links. This avoids
    # modifying 19 original 5k-record export files on each incremental refresh.
    overlays = {}
    for overlay_file in sorted((DATA / "enriched").glob("ats-*.json")):
        overlay = json.loads(overlay_file.read_text(encoding="utf-8"))
        records = overlay.get("records", {})
        if not isinstance(records, dict):
            raise ValueError("Unexpected employer-description overlay")
        for canonical_key, details in records.items():
            if isinstance(details, dict) and isinstance(details.get("description_excerpt"), str):
                overlays[canonical_key] = details
    if overlays:
        from urllib.parse import urlsplit
        for row in jobs:
            url = row.get("apply_url") or ""
            parts = urlsplit(url)
            canonical_key = (parts.netloc.lower() + parts.path).rstrip("/").removesuffix("/application").lower()
            details = overlays.get(canonical_key)
            if details and (not row.get("description_excerpt") or
                            len(details["description_excerpt"]) > len(row.get("description_excerpt") or "")):
                row["description_excerpt"] = details["description_excerpt"]
                row["description_source"] = details.get("description_source", "")
            if details and details.get("sponsorship") in ("stated", "conditional", "unavailable"):
                if row.get("review") != "manual":
                    row["sponsorship"] = details["sponsorship"]
                    row["evidence"] = details.get("evidence", "")
                    row["evidence_source"] = details.get("evidence_source", "")
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
            "industry", "job_function", "experience_level", "salary", "work_arrangement",
            "sponsorship", "evidence", "evidence_source", "evidence_url",
            "apply_url", "verified_on", "posted_at", "last_seen", "active",
            "review", "summary", "source_attribution", "posting_attribution",
            "description_excerpt", "description_source",
        )
    } for job in selected]
    # Static Pages cannot query a server-side database. Split large indexes
    # so no single public file becomes tens of megabytes.
    chunk_paths = []
    if len(selected) > 5000:
        dirpath = OUT / "data" / "jobs"
        dirpath.mkdir(parents=True)
        for start in range(0, len(selected), 5000):
            name = "chunk-%03d.json" % (start // 5000 + 1)
            (dirpath / name).write_text(
                json.dumps({"jobs": selected[start:start + 5000]},
                           ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            chunk_paths.append("./data/jobs/" + name)
    public_jobs = {
        "updated_at": jobs_source.get("updated_at"),
        "mode": "automated",
        "coverage_note": "All collected jobs; visa sponsorship not implied. Check original employer advert.",
        "jobs": [] if chunk_paths else selected,
        "chunks": chunk_paths,
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
