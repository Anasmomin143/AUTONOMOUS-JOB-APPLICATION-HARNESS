---
name: job-scoring
description: Score jobs 0-100 against the user's master profile using weighted categories (technical skills, experience, responsibilities, domain, seniority, ATS keywords, education). Use when the user wants to prioritize or triage discovered jobs.
---

# job-scoring

Backing CLI: `python -m harness.cli score [--job <id>]`.

Weights and thresholds live in `config/scoring.yaml`. Do not inflate
scores. Show the user the per-category breakdown and the missing skills
list — those are what tailoring will fix.
