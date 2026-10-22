# UK Sponsorship Jobs — connected beta (private)

Lightweight UK vacancies directory designed around **three separate evidence types**: a job advert's sponsorship statement, a precise current Skilled Worker register match, and previous sponsorship records where independently sourced.

**Status:** code integrated but not yet deployed; data feeds require the first successful GitHub Actions run. Prototype listings dated 22 October 2026 must not be advertised as current unless refreshed.

## Data and costs

- Home Office sponsor register: official CSV, checked once daily. A name-only match is marked *possible*, not independently verified; exact, curated legal entity match is required for verified status. The CSV has no previous CoS counts.
- Job listings: public, read-only Ashby/Greenhouse job-board feeds listed in `data/sources.json`; check each employer board's usage terms before production. Hourly schedule is best-effort. Text classification is conservative, and links go directly to the source.
- Historical CoS: `data/history.csv` is a **source-audited import interface**, not a fabricated database. Add only employer-level official FOI figures after confirming the legal name, metric (assigned vs used), year, suppression rules and source URL. There are no historical employer counts pre-populated.
- Sponsor history captured from the first successful register check: `first_observed_on` means **the first day this project observed a listing**, not the date the company was licensed or a previous sponsorship event.
- No user accounts, trackers, paid database, images, fonts, frameworks or secrets. Only small JSON files are published.

## How to run locally

```bash
python -m unittest discover -s tests -v
python scripts/refresh.py --offline
python -m http.server 8000
```

Visit http://localhost:8000. A real refresh requires internet connectivity and access to public job feeds.

## GitHub Actions

The `refresh.yml` workflow checks configured feeds hourly, the register daily, validates output, and commits changed data back to `main`. GitHub scheduling may be delayed or skipped and public feeds can change without warning. Failed register checks keep the most recent valid data; stale timestamps remain visible. `refresh.yml` does not publish a private repo.

For **GitHub Free**, Pages requires a public repository. Once reviewed and made public, activate GitHub Pages with **Settings → Pages → Source: GitHub Actions** and enable the optional `deploy.yml` workflow. This workflow only deploys if the repository is public. The site is not presently live.

## Sponsor source

https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers

## Research on historical disclosure

- Home Office FOI 2025/12841 (2021–2024 CoS assignments), via WhatDoTheyKnow: https://www.whatdotheyknow.com/ . Download original annex before importing; values suppressed by Home Office must remain suppressed.
- Home Office FOI2026/03501 for 2025 CoS used; do not combine "used" with prior-year "assigned" as if identical.

**No sponsorship guarantee or immigration advice is provided.**
