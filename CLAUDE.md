# Autonomous Job Application Harness — Claude Instructions

This is a human-supervised job-application harness. Slash commands under
`.claude/commands/` shell into `python -m harness.cli …` (source lives in
`scripts/harness/`). JSON under `jobs/`, `applications/`, `state/` is the
automation's source of truth; the Excel at `tracker/Job_Application_Tracker.xlsx`
is a one-way projection for humans.

## Non-negotiables

1. **Never fabricate profile facts.** Employment, titles, dates, skills,
   metrics, technologies, projects, certifications, education,
   management experience — all must be present in
   `profile/master-profile.md`. If a bullet, cover letter, screening
   answer, or recruiter message would need something outside that file,
   STOP and ask.
2. **Never claim success without verification.** Every action (form fill,
   upload, submit, email send) must be verified against page state,
   returned status, or a matched confirmation.
3. **Never bypass CAPTCHA, MFA, OTP, anti-bot, or login protections.**
   When encountered, stop and hand the browser to the user.
4. **Never submit an application without explicit approval** unless BOTH
   `config/automation-policy.yaml` has `mode: autonomous` +
   `allow_application_submission: true` AND `/mode autonomous` has been
   confirmed via the two-step YES in this session.
5. **Never apply twice** to the same job (dedupe by URL, requisition ID,
   or company+role).
6. **Silence is not approval.**

## Layout

```
config/                   YAML: settings, scoring, automation-policy
profile/                  master-profile.md, master-resume.pdf, linkedin.md, preferences.md
jobs/                     discovered.json, qualified.json, rejected.json, archive.json
applications/             applications.json, followups.json, interviews.json + per-app checkpoints
resumes/master/           parsed master resume JSON
resumes/tailored/         per-application PDFs, named <Company>_<Role>_<APP-ID>.pdf
messages/                 recruiter and follow-up templates + sent history
tracker/                  Job_Application_Tracker.xlsx + activity_log.md
reports/                  daily/, weekly/
scripts/harness/          Python package (all business logic)
skills/                   Project-local skills invoked by other Claude sessions
.claude/commands/         Slash-command definitions
state/                    Runtime state (STOP sentinel, mode confirmations, counters)
```

## Running a slash command

Each `.claude/commands/<name>.md` shells to `python -m harness.cli
<subcommand> [args]`. That Python entry point:

- Reads `config/*.yaml`.
- Reads/writes JSON via `harness.state` (atomic tmp+rename).
- Writes to `tracker/activity_log.md` for every state change.
- Updates the Excel projection via `harness.tracker.excel`.
- Uses `mcp__Gmail__*` for email (through a shim; Claude routes the
  MCP calls itself when the CLI prints a JSON envelope on stdout).

When the CLI prints a line matching `HARNESS_REQUEST: <verb> <json>`,
the slash-command wrapper is expected to perform that action (Playwright
launch, MCP tool call, user approval prompt) and echo the result back
via `harness.cli --resume <request-id>`.

## Approval gate

When `/apply` reaches submission, the CLI prints the APPLICATION READY
block (see §14 of the spec) and writes
`applications/<APP-ID>/pending_approval.json`. The slash-command wrapper
must ask the user `Approve? YES / NO`. Silence is NO.

## Autonomous mode

`/mode autonomous` requires:

1. `config/automation-policy.yaml`: `mode: autonomous` +
   `allow_application_submission: true`.
2. The user types the exact word `YES` twice at the two prompts.
3. Every mode change is appended to `state/mode-log.md`.

Any missing lock forces the supervised approval gate; the CLI refuses
to auto-submit.

## Verified vocabulary

`harness.resume.validate` extracts an allowlisted vocabulary from
`profile/master-profile.md` (employers, titles, technologies, metrics,
projects, dates). Any tailored bullet containing a token outside that
allowlist is rejected. Three rejections in a row → stop and ask the user.
