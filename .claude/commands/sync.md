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

Two-step:

1. `python -m harness.cli sync` emits `HARNESS_REQUEST: gmail_search
   {...}` lines, one per application.
2. For each request, call `mcp__Gmail__search_threads` with the given
   query, then `mcp__Gmail__get_thread` for each hit, collecting
   `{subject, from, body}` into a single JSON file at
   `state/mailbox-<timestamp>.json` (schema: `{"messages": [ ... ]}`).
3. Feed it back:
   `python -m harness.cli sync --ingest state/mailbox-<timestamp>.json`.
4. The CLI matches messages using ≥2 independent signals, reconciles
   Tracker vs ATS vs Email statuses, and writes to
   `applications/applications.json` + Excel.

Do NOT update an application on a weak (1-signal) match — the CLI marks
those `[review]` in notes; escalate to the user instead.
