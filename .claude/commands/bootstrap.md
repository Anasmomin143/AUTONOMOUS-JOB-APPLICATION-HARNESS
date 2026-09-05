---
description: Initialize the harness — scaffold, probe browser, seed profile check.
allowed-tools:
  - Bash(python -m harness.cli bootstrap)
  - Read
  - Write
---

# /bootstrap

Runs the harness bootstrap:

1. Creates the full directory tree if missing.
2. Seeds empty JSON stores (`jobs/*.json`, `applications/*.json`, counters).
3. Regenerates `tracker/Job_Application_Tracker.xlsx` (empty).
4. Prints a REPORT block showing:
   - profile readiness (whether `master-profile.md` still has TODO(user) blocks),
   - Playwright browser availability,
   - current mode (supervised / autonomous) and lock state.

Never submits a job. Never enables autonomous mode.

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli bootstrap
```

After the report, if any `TODO(user)` block is listed as unresolved, walk
the user through them one at a time before running any other command.
