# SponsorHQ — UK Jobs & Sponsorship Evidence (public beta)

Lightweight UK vacancies directory designed around **three separate evidence types**: a job advert's sponsorship statement, a precise current Skilled Worker register match, and previous sponsorship records where independently sourced.

**Status (22 October 2026):** GitHub data refresh has collected employer-feed jobs and matched current Skilled Worker sponsor-register entries for Ankar, Neudata and Mistral AI. The repository has been made public for a free GitHub Pages beta. The Pages deployment must still complete successfully before the live website is available. Sponsorship history counts remain unpopulated until separately sourced.

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

## Verified data milestone

The initial job importer and sponsor-register matcher have written records to `data/jobs.json` and `data/sponsors.json`. The current three companies with a curated legal-entity match are **Ankar (ANKAR.AI LTD / Ankar.ai)**, **Neudata (NEUDATA LIMITED)**, and **Mistral AI (MISTRAL AI UK LTD / Mistral AI UK Limited)**. These are licence matches, not promises that each role offers sponsorship. The register has no historical Certificate of Sponsorship counts. Any unverified employer or missing history stays explicitly marked unknown.


## Free launch checklist (GitHub Pages)

The repository is now **public**, meeting the visibility requirement for GitHub Free Pages. Review the source repository before sharing the website broadly.

Next select **Settings → Pages → Build and deployment → Source: GitHub Actions**. Do **not** choose Deploy from a branch. In **Actions**, manually run **Deploy public job board** once if it does not start automatically. The expected Pages URL is:

https://yogeshkaransharma-code.github.io/uk-sponsorship-jobs/

The deployment workflow builds `_site/` using `scripts/build_site.py`. It publishes only the minimal static files and active vacancies observed within the last 14 days. Hourly importer completions trigger new Pages deployments through `workflow_run`; pushes made by the standard Actions token would not trigger a normal `push` deployment. GitHub schedules are best-effort, not exact.

**Launch status:** This is an early public beta with a very small employer feed. Sponsor licence evidence is not proof the advertised role offers sponsorship. The history CSV is not yet populated, so employer-level historical CoS counts are still unavailable. Before sharing widely, confirm all employer links, independent entity matches and the first deployed Pages run.


## Road to 100,000 UK jobs — zero-cost integration

**Prepared, not yet imported.** SponsorHQ's current self-run 19 employer feeds remain separate from an optional Headcount Labs bulk import. The third-party provider reported around 185,879 GB jobs on 21 October 2026; that is **not** a count on SponsorHQ. A free Headcount Labs account currently gives 100,000 returned job records **per UTC calendar month**, not per day. Repeated delivery of the same record also counts. Never enable optional paid usage; leave the vendor's default **$0 paid usage cap** in place.

Only the account owner can create the key:

1. Register free at https://api.headcountlabs.com/data/signup and get an API key at https://api.headcountlabs.com/data/keys.
2. In GitHub, add repository **Actions secret** `HEADCOUNTLABS_API_KEY` in **Settings → Secrets and variables → Actions**. **Never paste the key into the repository, an issue, a chat or a screenshot.**
3. Run **Actions → Import UK job-data snapshot (manual, free allowance only) → Run workflow**. It is intentionally not scheduled, and it imports no data if no key is present.

`scripts/import_headcount.py` uses the documented bulk-export endpoint with `country=GB`, `currentness=current` and a maximum of 100,000 jobs. The importer rejects non-UK, closed and invalid-link records, normalizes fields and commits a compact snapshot to `data/bulk/jobs.json` and `data/bulk/manifest.json`. The existing Pages workflow reads the optional index and merges it with current employer feeds. This **does not guarantee 100,000 unique, current, verified jobs**; missing locations, duplicate links, jobs closing, source coverage and monthly record limits reduce the resulting count. Sponsorship defaults to **unknown** for every imported record because the snapshot has no verified vacancy-specific sponsorship statement.

Source: https://headcountlabs.com/terms/ ; licence: https://headcountlabs.com/license/ ; bulk export docs: https://headcountlabs.com/docs/bulk-download/ . Headcount Labs licenses its own contributions under CC BY 4.0; descriptions, names, logos and employers' works may have other rights. Keep only compact metadata and link to the original posting. Required credit: "Job data: Headcount Labs (https://headcountlabs.com), CC BY 4.0. Job postings belong to their publishers."

For durable nationwide operation at 100k+ current vacancies, replace the first-release browser-wide JSON approach with paginated indexed search, manage expired adverts and incremental update events, and ensure adequate lawful data rights. GitHub Pages alone is a first-stage static prototype, not a production-grade job search database.
