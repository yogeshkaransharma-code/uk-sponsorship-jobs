#!/usr/bin/env python3
"""One-time, opt-in UK job import using the Headcount Labs free API allowance.

Run only when explicitly dispatched. Requires HEADCOUNTLABS_API_KEY set as
a GitHub Actions secret. We never enable paid usage. The vendor enforces a
$0 paid-usage cap by default; verify it in the provider account too.

Only a small metadata index with links to employer postings is published.
Do not imply a vacancy offers visa sponsorship when that is not stated.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ENDPOINT = "https://api.headcountlabs.com"
LIMIT = 100_000
FIELDS = [
    "job_id", "currentness", "employer_name", "title", "description",
    "work_arrangement", "locations", "job_first_seen_at", "postings",
]


def unwrap(value):
    if isinstance(value, dict):
        return value.get("value") if value.get("state") in ("known", "derived") else None
    return value


def api(path, *, key, method="GET", payload=None):
    if not path.startswith("/v1/jobs/"):
        raise ValueError("Unexpected API path")
    u = urlparse(urljoin(ENDPOINT, path))
    if u.scheme != "https" or u.hostname != "api.headcountlabs.com":
        raise ValueError("Unexpected API host")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(u.geturl(), data=data, method=method,
                  headers={"Authorization": "Bearer " + key,
                           "Accept": "application/json",
                           "Content-Type": "application/json",
                           "User-Agent": "SponsorHQ-public-jobs/0.1"})
    with urlopen(req, timeout=60) as response:
        return json.loads(response.read(5_000_000))


def download(path, *, key):
    u = urlparse(urljoin(ENDPOINT, path))
    if u.scheme != "https" or u.hostname != "api.headcountlabs.com" or not u.path.startswith("/v1/jobs/exports/"):
        raise ValueError("Unexpected export URL")
    req = Request(u.geturl(), headers={"Authorization": "Bearer " + key,
                                       "User-Agent": "SponsorHQ-public-jobs/0.1"})
    with urlopen(req, timeout=120) as response:
        return response.read(100_000_000)


def good_url(url):
    return isinstance(url, str) and url.startswith("https://") and bool(urlparse(url).hostname)



def infer_function(title):
    """Broad job-function grouping from title, not employer industry."""
    mapping = (
        ("Insurance & Claims", r"\b(underwrit|claims|actuar|insurance|broker|reinsur)"),
        ("Sales & Relationships", r"\b(sales|account|business development|relationship|partnership|customer success|client)"),
        ("Finance & Accounting", r"\b(financ|accountan|audit|tax|treasury|controller)"),
        ("Technology & Engineering", r"\b(engineer|developer|software|devops|architect|platform|cyber|security)"),
        ("Data & Analytics", r"\b(data|analytic|scientist|machine learning|statistic)"),
        ("Healthcare", r"\b(health|nurs|medical|clinic|physician|therapist|pharmac)"),
        ("Education", r"\b(teacher|lecturer|professor|tutor|school|education)"),
        ("Operations & Support", r"\b(operation|support|service|administrator)"),
        ("Marketing & Communications", r"\b(marketing|content|brand|communications)"),
        ("People & HR", r"\b(recruit|talent|human resources|hrbp|people partner)"),
    )
    for label, pattern in mapping:
        if re.search(pattern, title, re.I):
            return label
    return "Other"


def infer_seniority(title):
    if re.search(r"\b(graduate|intern|apprentice|trainee)\b", title, re.I):
        return "Graduate / trainee"
    if re.search(r"\b(junior|entry.level|assistant)\b", title, re.I):
        return "Junior / entry"
    if re.search(r"\b(chief|ceo|cfo|cto|vp|vice president|director|head of)\b", title, re.I):
        return "Leadership"
    if re.search(r"\b(senior|lead|principal|staff)\b", title, re.I):
        return "Senior"
    return "Not specified"

def record(row):
    if not isinstance(row, dict) or row.get("currentness") != "current":
        return None
    company = unwrap(row.get("employer_name"))
    title = unwrap(row.get("title"))
    if not isinstance(company, str) or not company.strip() or not isinstance(title, str) or not title.strip():
        return None
    places = []
    for entry in row.get("locations") or []:
        loc = unwrap(entry)
        if isinstance(loc, dict) and loc.get("country") == "GB":
            places.append(loc)
    if not places:
        return None
    postings = row.get("postings") or []
    selected = None
    for p in postings:
        if not isinstance(p, dict) or p.get("posting_status") != "listed":
            continue
        url = unwrap(p.get("application_url")) or unwrap(p.get("posting_url"))
        if good_url(url):
            selected = (p, url)
            break
    if not selected:
        return None
    p, url = selected
    attribution = p.get("attribution") or {}
    required = attribution.get("required") is True
    credit_text = attribution.get("text")
    credit_link = attribution.get("link")
    if required and not isinstance(credit_text, str):
        # Honour publisher-required attribution rather than removing rights data.
        return None
    posting_credit = None
    if required:
        posting_credit = {"text": credit_text.strip()[:200],
                          "link": credit_link if good_url(credit_link) else url}
    city = next((x.get("city") for x in places if x.get("city")), None)
    region = next((x.get("region") for x in places if x.get("region")), None)
    location = (city or region or "United Kingdom") + ", UK" if city or region else "United Kingdom"
    pay = unwrap(p.get("pay"))
    salary = "Not disclosed"
    if isinstance(pay, dict) and pay.get("currency") == "GBP" and pay.get("interval") == "year":
        mn, mx = pay.get("min"), pay.get("max")
        if isinstance(mn, (float, int)) and isinstance(mx, (float, int)):
            salary = "£{:,.0f}–£{:,.0f} per year".format(mn, mx)
    ident = row.get("job_id")
    if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9-]{10,60}", ident):
        return None
    # Future free monthly snapshots also include short advert excerpts.
    # Keep copies small; original advert has the full, authoritative text.
    import html
    original=unwrap(row.get("description"))
    if not isinstance(original,str):original=""
    plain=html.unescape(re.sub(r"<[^>]+>", " ", original))
    plain=re.sub(r"\s+", " ", plain).strip()
    excerpt=plain[:750].rstrip()
    if len(plain)>750 and " " in excerpt:
        excerpt=excerpt.rsplit(" ",1)[0]+"…"
    # Identify wording in the actual advert conservatively. This remains
    # automated evidence; users must check employer wording before applying.
    status,evidence=("unknown","No description collected for visa analysis")
    if plain:
        from refresh import classify
        status,evidence=classify(plain[:15000])
    arrangement=unwrap(row.get("work_arrangement"))
    arrangement=arrangement if arrangement in ("remote","hybrid","in_person") else ""
    return {
        "id": "headcount-" + ident, "company": company.strip(),
        "legal_name": "", "title": title.strip(),
        "location": location, "country": "GB",
        "category": "Industry not verified",
        "industry": "Other / unclassified",
        "job_function": infer_function(title),
        "experience_level": infer_seniority(title),
        "salary": salary, "sponsorship": status, "evidence": evidence,
        "work_arrangement": arrangement,
        "description_excerpt": excerpt,
        "evidence_source": "Automatically detected advert wording, via Headcount Labs" if plain else "Headcount Labs metadata (description absent)",
        "evidence_url": url, "apply_url": url,
        "verified_on": (row.get("job_updated_at") or "")[:10] or (row.get("job_first_seen_at") or "")[:10],
        "posted_at": (p.get("source_posted_at") or "")[:10],
        "last_seen": time.strftime("%Y-%m-%d", time.gmtime()),
        "active": True, "review": "auto",
        "summary": "UK vacancy listed on the employer's recruitment system. Visa policy not confirmed.",
        "source_attribution": "Headcount Labs",
        **({"posting_attribution": posting_credit} if posting_credit else {}),
    }


def normalize_export(rows):
    out = {}
    for row in rows:
        value = record(row)
        if value:
            out[value["id"]] = value
    return sorted(out.values(), key=lambda x: (x["company"].casefold(), x["title"].casefold()))


def main():
    key = os.environ.get("HEADCOUNTLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing HEADCOUNTLABS_API_KEY GitHub Actions secret. Nothing was downloaded.")
    maximum = min(LIMIT, int(os.environ.get("HEADCOUNT_MAX_JOBS", LIMIT)))
    if maximum < 1:
        raise SystemExit("A positive maximum is required")
    print("Verifying access and free UK job count (count requests are not billable)…", flush=True)
    counts = api("/v1/jobs/count?country=GB&currentness=current", key=key)
    print("Provider UK available-count response: {}".format(str(counts)[:200]), flush=True)
    print("Requesting GB-only current jobs, maximum {} (manual import, not recurring)".format(maximum), flush=True)
    try:
        response = api("/v1/jobs/exports", key=key, method="POST", payload={
            "country": "GB", "currentness": ["current"], "max_records": maximum,
            "fields": FIELDS,
        })
    except HTTPError as exc:
        # The API may return a machine-readable validation message. Never log
        # the bearer key or the contents of the Authorization header.
        detail = exc.read(3000).decode("utf-8", "replace").replace(key, "[REDACTED]")
        print("Bulk export refused (HTTP {}): {}".format(exc.code, detail[:1800]), file=sys.stderr)
        raise
    export_id = response.get("export_id")
    if not isinstance(export_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,100}", export_id):
        raise ValueError("API did not return a safe export ID")
    status = None
    for attempt in range(150):
        status = api("/v1/jobs/exports/" + export_id, key=key)
        if status.get("status") in ("completed", "failed", "expired"):
            break
        time.sleep(10)
    if not status or status.get("status") != "completed":
        raise RuntimeError("Import did not complete: " + str((status or {}).get("status")))
    rows = []
    files = status.get("files", [])
    if len(files) > 20:
        raise ValueError("Unexpected number of export chunks")
    for chunk in files:
        blob = download(chunk["url"], key=key)
        for line in gzip.decompress(blob).splitlines():
            if line:
                rows.append(json.loads(line))
        print("Downloaded {} of {} chunks, {} rows".format(files.index(chunk)+1, len(files), len(rows)), flush=True)
    items = normalize_export(rows)
    if not items:
        raise RuntimeError("Import returned no valid UK vacancies; existing records untouched")
    out = DATA / "bulk"
    out.mkdir(exist_ok=True, parents=True)
    # Each file stays well below GitHub's 100 MB per-file limit.
    # A single 100k-record JSON would be too large to maintain in Git.
    for old_file in out.glob("headcount-*.json"):
        old_file.unlink()
    chunk_size = 5000
    for offset in range(0, len(items), chunk_size):
        number = offset // chunk_size + 1
        dest = out / ("headcount-%03d.json" % number)
        dest.write_text(json.dumps({"jobs": items[offset:offset + chunk_size]},
                                   ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "provider": "Headcount Labs",
        "terms": "https://headcountlabs.com/terms/",
        "attribution": "Job data supplied by Headcount Labs (https://headcountlabs.com). Original adverts belong to employers.",
        "imported_on": time.strftime("%Y-%m-%d", time.gmtime()),
        "fetched_records": len(rows), "valid_uk_jobs": len(items),
        "chunks": (len(items) + chunk_size - 1) // chunk_size,
        "source": "https://headcountlabs.com/",
    }, indent=2) + "\n", encoding="utf-8")
    print("Prepared {} UK jobs for SponsorHQ's next deployment".format(len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
