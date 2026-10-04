---
description: Reconcile applications against Gmail + ATS + tracker.
allowed-tools:
  - Bash(python -m harness.cli sync *)
  - mcp__Gmail__search_threads
  - mcp__Gmail__get_thread
  - Read
  - Write
---

# /sync

Before searching, check that the connected Gmail account is the one
applications use (`contact_email_for_applications` in
`profile/preferences.md`). If it isn't, say so and stop — another inbox
holds none of the replies.

1. `python -m harness.cli sync` emits one `HARNESS_REQUEST: gmail_search
   {...}` line per **submitted** application, with a query already
   limited to mail since it was sent.
2. For each request, call `mcp__Gmail__search_threads` with the given
   query, then `mcp__Gmail__get_thread` for each hit. Write every message
   into one JSON file at `state/mailbox-<timestamp>.json`:
   `{"messages": [{"id", "date", "from", "subject", "body"}]}` — `id` is
   the Gmail message id (re-ingesting is then a no-op), `date` the Date
   header or Gmail's internal epoch-milliseconds, `body` plain text.
3. Feed it back:
   `python -m harness.cli sync --ingest state/mailbox-<timestamp>.json`.
4. Report the CLI's `UPDATED` and `REVIEW` lines to the user.

How the CLI decides (`harness.email`):

- A status changes only when the email names the company (sender domain
  or text) **and** something specific to the job (role title,
  requisition ID, application ID or job URL). Your own name is not
  evidence. Anything weaker becomes a `[review]` note, never a change.
- Statuses only move forward (APPLIED → CONFIRMED → ASSESSMENT →
  INTERVIEW); a rejection or offer applies from anywhere. Emails are
  applied oldest first; mail from before the application is ignored.
- A `REVIEW` line naming several applications matched them equally —
  ask the user which one it is; do not edit `applications.json` to guess.
