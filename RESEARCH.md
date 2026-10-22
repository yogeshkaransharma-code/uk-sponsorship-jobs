# UK sponsorship job platforms: competitor audit and product direction

**Research date:** 22 October 2026. Based on publicly accessible pages and documented statements, not logged-in tests. This is a representative review of UK-specific and UK-accessible tools, **not** a claim to have inspected every UK jobs website.

## The market is already active

| Platform | What its public pages say it does | Relevant strategic lesson / opportunity |
|---|---|---|
| Hunt UK Visa Sponsors (huntukvisasponsors.com) | Large careers-page jobs index, historic visa issuance trends, occupation-code / pay likelihood, alerts; public method warns predictions aren't guarantees. | Historical sponsorship + likelihood are **not** unique. Compete with simplicity, primary evidence and no false precision, not “we invented company history”. |
| KnowYourSponsor (knowyoursponsor.co.uk) | Daily sponsor register comparisons, Companies House enrichment, detailed primary FOI methodology and separate 2025 CoS use disclosure. | Data quality and conservative identity matching matter. Do not copy their proprietary work; use official publications independently. |
| SponsorJobs (sponsorjobs.co) | New jobs every hour; claims adverts checked and explicitly excluded non-sponsors filtered; licensed-company checks. | Hourly freshness is already a competitor feature. We must display the *actual last successful check* and rule evidence. |
| hire.moi (hire.moi/visa-sponsorship) | Explicit advert offers separate from jobs at licensed employers, with direct listings. | Good category separation; our extra value is accessible history and documented caveats without complexity. |
| UK Visa Jobs (ukvisajobs.com) | Large board and sponsor directory; public counts, membership model for full job browsing. | No paywall, employer links, no email registration. Public listing counts are self-reported, not audited here. |
| Visa Sponsorship Hub (visasponsorshiphub.com) | Sponsor register linked to hiring companies, salary screening, careers-page indexing. | Big databases are already common; history quality and explanation matter more. |
| Sponsored Jobs UK (sponsoredjobs.uk) | Smaller publicly browsable vacancies at verified sponsoring employers. | “Verified sponsor” does not itself establish role-specific eligibility. |
| SkilledJobs (skilledjobs.com) | Employer-licensed job board, refreshed daily with some paid access. | Keep the core utility free and immediately accessible. |
| Student Circus (studentcircus.com via university partners) | Visa-oriented jobs, country guidance, placements for international students/graduates. | Useful existing tool, but access can depend on university relationship. Serve all jobseekers. |
| GradSponsor (gradsponsor.co.uk) | Sponsorship signals, filters, free/paid levels. | Data normalisation is vital; its visible board has examples of suspicious salary presentation such as “Up to £5” and “££”. Avoid publishing unusable salary figures. |
| JLocate (jlocate.com) | Hand-checked small public board, vacancy checker and comparison research. | Small and accurate is an acceptable starting point; we can lean into minimalism. |
| SponsorMap (sponsormap.uk) | Sponsor register directory, licence checks, jobs and filters. | Directory alone is insufficient to differentiate. |
| Free Movement dashboard (updates.freemovement.org.uk) | Daily register snapshots and search; historical membership features. | Register history (appearing/disappearing) is not CoS issuance history. Clearly separate them. |

## Product positioning

**One screen, three verifiable answers:**

1. **What does this exact advert say?** Clearly state: offers visa sponsorship / considers individually / no statement (worth checking with verified licence) / rules it out.
2. **Is the actual employing legal entity licensed for the relevant route?** Verified legal name, route, rating, checked date, official CSV. An unverified name match is clearly labelled as such.
3. **Has it sponsored in the past?** Show separately sourced CoS assignment/use figures by year/route *only where identity match and publication are reliable*. Show “No reliable history available” rather than zero.

No arbitrary 93% 'visa chance' numbers. Eligibility varies with the occupation code and the individual's circumstances.

## Three key data truths

- GOV.UK's Worker and Temporary Worker **sponsor register** is authoritative for the published licence record, NOT job-specific sponsorship or historic visa grants. The file has organisations, towns, ratings and routes but not public sponsor licence IDs.
- A Home Office written parliamentary answer (12 January 2026) referred to table `SP_01` in sponsorship transparency datasets. Separately, FOI documents have disclosed historical employer-level CoS activity. A CoS **assigned** differs from CoS **used**, and neither necessarily equals a worker hired or a granted visa.
- Employer names, trading names, group subsidiaries and multiple locations often mismatch. Matching on similar strings may create false sponsor claims. Require exact unique legal identity corroboration; otherwise withhold the status.

Official public sources:
- https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers
- https://www.gov.uk/government/statistical-data-sets/migration-transparency-data
- https://questions-statements.parliament.uk/written-questions/detail/2026-01-02/101993/
- https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

Background methodology (independent, not a source to copy):
- https://knowyoursponsor.co.uk/methodology/

## How to stay at £0 per month

- **Front end:** Static HTML, one CSS file, one JS file, no images, no external fonts, no npm/React, no analytics or cookies. A very small page.
- **Hosting:** GitHub Pages on a public GitHub Free repository. Free HTTPS on the github.io domain, no domain purchase. Configure branch deployment. No private user data or secrets are put into repository files.
- **Refresh:** GitHub Actions scheduled `17 * * * *`, using standard hosted runners on a public repository (free under current plan). Worker reads a short whitelist of employer public ATS boards and writes JSON snapshots, then Pages deploys changes.
- **Licence:** Government CSV retrieved daily as a single small processing job; only a tiny matched sponsor index is published, not a 10MB+ download forced upon every visitor.
- **History:** A curated, source-linked CSV from official FOI publications, updated when new public data becomes available, not hourly. Provenance is more important than update frequency.
- **Applications:** Direct external employer URLs; applicant documents never pass through the site.
- **External job feeds:** Ashby public job posting API and Greenhouse public job board GET endpoints. Their official documentation describes published roles and public access. But third-party republication/large-scale feed use must respect terms and publisher permission; avoid mass scraping.

Sources for feasibility:
- https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- https://developers.ashbyhq.com/docs/public-job-posting-api
- https://docs.greenhouse.io/job-board

## Limitations / risk register

1. **£0 isn't a legal or permanent guarantee.** Free-tier limits change, excessive loads can trigger throttling, and direct .com/.co.uk domains cost money. No paid custom domain at launch.
2. **Jobs every hour** means a scheduled check attempt, not that all employers or job feeds update hourly. Some jobs won't be discoverable in the sources we track.
3. **No verified history in the starter build.** The reviewed starter adverts demonstrate labels, but no employer-specific historical CoS counts should be guessed or lifted from another private database. Separate FOI verification/ingestion is a next step.
4. **Current-status checks** are separate from advert excerpts. Starter examples are not represented as guaranteed open; after the public-feed importer starts, cards say whether a successful feed has seen them.
5. **No visa eligibility guarantees.** Role-specific SOC code and going rate require checks; salary thresholds and new entrant arrangements must be verified from current official rules.
6. **GitHub Actions schedules are best-effort.** They may be delayed or occasionally dropped. The UI states the last successful refresh.
7. **GitHub Pages is simpler but doesn't set custom security HTTP headers.** Its strongest property for this MVP is being entirely static with no applicant data collected. The provided `_headers` works on Cloudflare Pages if migrated.
8. **Attribution:** The Open Government Licence permits reuse of licensed public information with appropriate acknowledgement. Employer adverts should be quoted briefly and linked, not bulk copied.

## MVP decision

Ship the simple, free, transparent job-linking tool. Start with a few dozen *high-quality employer feeds*, ideally financial services, insurance, technology and commercial sales, before expanding into all industries. Add historic employer CoS disclosure in a fully sourced format before marketing any “past sponsor” filter. Do not prioritise registrations, AI scoring, CV builders, paid plans or graphics.
