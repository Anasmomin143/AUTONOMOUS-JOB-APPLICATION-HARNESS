---
name: application-sync
description: Reconcile applications against Gmail (via mcp__Gmail__*) and ATS state, changing a status only when the email names both the company and the specific job. Use for /sync and before /followup.
---

# application-sync

Backing CLI:
- `python -m harness.cli sync` → Gmail-search requests for submitted
  applications, each limited to mail since the application date.
- Wrapper calls `mcp__Gmail__search_threads` + `get_thread`, writes
  `state/mailbox-<ts>.json` as `{"messages": [{"id", "date", "from",
  "subject", "body"}]}`.
- `python -m harness.cli sync --ingest <path>` → matches, classifies and
  updates; prints `UPDATED` / `REVIEW` lines.

Rules (`harness.email.match`, `harness.email.sync`):
- High confidence = company evidence (sender domain or name in text) +
  job evidence (role, requisition ID, application ID or job URL). The
  candidate's name never counts. Weaker matches are `[review]` notes.
- Classification is by phrase, in priority order REJECTED, OFFER,
  INTERVIEW, ASSESSMENT, CONFIRMED; conditional sentences ("if selected,
  we'll schedule an interview") announce nothing.
- Status moves forward only; REJECTED / OFFER end the funnel. Messages
  are applied oldest first, de-duplicated by Gmail id (`email_events`).
