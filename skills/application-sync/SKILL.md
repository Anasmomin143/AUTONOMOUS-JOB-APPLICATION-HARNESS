---
name: application-sync
description: Reconcile applications against Gmail (via mcp__Gmail__*) and ATS state, updating the tracker only when at least two independent signals match. Use for /sync and before /followup.
---

# application-sync

Backing CLI:
- `python -m harness.cli sync` → emits Gmail-search requests.
- Wrapper calls `mcp__Gmail__search_threads` + `get_thread`, writes
  `state/mailbox-<ts>.json`.
- `python -m harness.cli sync --ingest <path>` → matches and updates.

Two-signal minimum (spec §17-19). Weak matches become `[review]` notes,
never silent state changes.
