---
description: Resume a failed application from its last checkpoint.
argument-hint: <APP-ID>
allowed-tools:
  - Bash(python -m harness.cli retry *)
  - Read
---

# /retry

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli retry "$1"
```

Marks the application `RETRY_PENDING`. Re-run `/apply 1 --role …` (or a
targeted `/apply`) to re-enter the browser flow from the last saved
checkpoint under `applications/<APP-ID>/checkpoints/`.
