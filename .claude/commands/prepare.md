---
description: Prepare a single qualified job through to READY_FOR_APPROVAL.
argument-hint: <job-id>
allowed-tools:
  - Bash(python -m harness.cli prepare *)
  - Read
---

# /prepare

Full preparation pipeline for one job:

1. Load the qualified job by ID.
2. Decide master vs tailored (`resume/decide.py`).
3. If tailored: build → validate against master-profile allowlist → render PDF.
4. Register the application, status = `READY_FOR_APPROVAL`, resume
   filename recorded per `<Company>_<Role>_<APP-ID>.pdf`.

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli prepare --job-id "$1"
```

If the validator rejects the tailored resume, DO NOT proceed. Show the
rejection reasons to the user and ask what to change in
`profile/master-profile.md`.
