# Autonomous Job Application Harness

Human-supervised job-search + application system, driven from Claude Code
via slash commands. Truthful (never fabricates profile facts), auditable
(every action logged, JSON + Excel synchronized), and resumable (failed
applications preserve state for `/retry`).

## Workflow

```
JOB DISCOVERY
  → JOB MATCHING (0-100 score)
  → COMPANY RESEARCH
  → RESUME DECISION (master vs tailored)
  → RESUME TAILORING (fact-checked)
  → APPLICATION PREPARATION
  → PLAYWRIGHT BROWSER AUTOMATION
  → HUMAN APPROVAL  ← default gate
  → APPLICATION SUBMISSION
  → EMAIL / ATS VERIFICATION
  → EXCEL TRACKER UPDATE
  → FOLLOW-UP
```

## First-run setup

1. `pip install -e .` (installs `harness` CLI + Python deps).
2. `python -m playwright install chromium` is **not** required — the
   pre-installed browser at `/opt/pw-browsers/chromium` is used.
3. Open Claude Code in this repo and run `/bootstrap`.
4. Resolve every `TODO(user)` block in `profile/master-profile.md`
   (six known conflicts between your resume and LinkedIn are marked).
5. Fill `profile/preferences.md` (roles, locations, salary floor,
   sponsorship, blocklist).
6. Add Greenhouse/Lever/Ashby company slugs to `config/settings.yaml`.

## Slash commands

| Command | Purpose |
|---|---|
| `/bootstrap` | Verify environment, seed profile, create Excel + JSON stores. |
| `/find-jobs <n>` | Discover up to `n` jobs from configured sources. |
| `/score <id>` / `/score-all` | Score jobs 0-100 per `config/scoring.yaml`. |
| `/research <company>` | Build a company brief. |
| `/prepare <id>` | Full prep: resume decide → tailor → validate → render → questions. |
| `/apply <n>` [`random`] [`--score N`] [`--role …`] [`--location …`] | Batch preparation & (supervised) submission. |
| `/sync` | Reconcile applications against Gmail + ATS. |
| `/followup` | Draft follow-ups (send requires approval). |
| `/status` | Dashboard. |
| `/retry <APP-ID>` | Resume the last checkpoint of a failed application. |
| `/stop` | Halt automation at the next boundary. |
| `/mode supervised\|autonomous\|status` | Two-lock autonomous toggle. |

## Safety defaults

`config/automation-policy.yaml` ships with:

- `mode: supervised`
- `allow_application_submission: false`
- `require_verified_resume: true`
- `stop_on_captcha / mfa / otp: true`
- `minimum_match_score: 85`

Autonomous submission requires **both** editing `automation-policy.yaml`
AND running `/mode autonomous` (two-step YES confirmation).

## Layout

See `CLAUDE.md`.
