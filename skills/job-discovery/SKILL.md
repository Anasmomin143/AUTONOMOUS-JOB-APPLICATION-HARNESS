---
name: job-discovery
description: Fetch and dedupe jobs from configured sources (Greenhouse, Lever, Ashby public boards work out of the box; LinkedIn/Indeed/Naukri/careers-page adapters need per-source setup). Use when the user asks to find jobs, refresh the pool, or add a new source.
---

# job-discovery

Backing CLI: `python -m harness.cli discover --count N`.

Enabled sources are configured in `config/settings.yaml` under
`discovery:`. Public ATS boards need only a company slug; login-gated
sources require a persistent Playwright user-data directory the user
seeds by logging in once manually.

Never fabricate jobs: if a source returns zero postings, report zero.
Never claim a job's location, salary, or requirement without a value
in the fetched record.
