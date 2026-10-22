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
    companies = dict(sponsor_source.get("companies", {}))
    candidate_file = DATA / "register_candidates.json"
    if candidate_file.exists():
        candidate_doc = json.loads(candidate_file.read_text(encoding="utf-8"))
        for brand, entry in candidate_doc.get("candidates", {}).items():
            if brand not in companies and entry.get("status") == "name_match":
                companies[brand] = entry
    if not isinstance(jobs, list) or not isinstance(companies, dict):
        raise ValueError("Incorrect public data format")

    # Do not publish expired editorial examples, malformed links or stale feeds.
    selected = []
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or job.get("active") is not True:
            continue
        if job.get("sponsorship") == "unavailable":
            # The site is specifically for people seeking possible sponsorship.
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
    # Keep initial page loads lightweight even as we recover thousands of
    # long job descriptions. Serve the longer employer text only when a reader
    # expands that job, in bounded, separately cached static JSON chunks.
    from hashlib import sha256
    full_descriptions = {}
    for job in selected:
        excerpt = job.get("description_excerpt")
        if not isinstance(excerpt, str) or len(excerpt) <= 340:
            continue
        key = sha256(job["apply_url"].encode("utf-8")).hexdigest()[:22]
        full_descriptions[key] = excerpt
        preview = excerpt[:310]
        if " " in preview:
            preview = preview.rsplit(" ", 1)[0]
        job["description_excerpt"] = preview + "…"
        job["description_key"] = key
    if full_descriptions:
        description_dir = OUT / "data" / "descriptions"
        description_dir.mkdir(parents=True, exist_ok=True)
        rows = list(full_descriptions.items())
        for start in range(0, len(rows), 120):
            filename = "part-%04d.json" % (start // 120 + 1)
            part = dict(rows[start:start + 120])
            (description_dir / filename).write_text(
                json.dumps(part, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            for key in part:
                # Map by content key to avoid a per-job file on GitHub Pages.
                full_descriptions[key] = "./data/descriptions/" + filename
        for job in selected:
            key = job.get("description_key")
            if key:
                job["description_ref"] = full_descriptions[key]
    # Publish only compact search metadata and preview snippets.
    selected = [{
        k: v for k, v in job.items()
        if k in (
            "id", "company", "legal_name", "title", "location", "category",
            "industry", "job_function", "experience_level", "salary", "work_arrangement",
            "sponsorship", "evidence", "evidence_source", "evidence_url",
            "apply_url", "verified_on", "posted_at", "last_seen", "active",
            "review", "summary", "source_attribution", "posting_attribution",
            "description_excerpt", "description_source", "description_key", "description_ref",
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
    return {
        "published_jobs": len(selected),
        "published_sponsor_entries": len(public_sponsors["companies"]),
        "jobs_with_readable_description": sum(bool(job.get("description_excerpt")) for job in selected),
        "sponsorship_stated": sum(job.get("sponsorship") == "stated" for job in selected),
        "sponsorship_conditional": sum(job.get("sponsorship") == "conditional" for job in selected),
        "sponsor_legal_identity_verified": sum(
            (public_sponsors["companies"].get(job.get("company"), {}).get("status") == "verified")
            for job in selected
        ),
        "possible_sponsor_name_matches": sum(
            (public_sponsors["companies"].get(job.get("company"), {}).get("status") == "name_match")
            for job in selected
        ),
    }


if __name__ == "__main__":
    print(json.dumps(build()))
