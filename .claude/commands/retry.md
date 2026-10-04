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

Marks a `FAILED` or `DECLINED` application `RETRY_PENDING` (anything
else is refused). Then `/submit <APP-ID>` runs the
browser flow again from the start of the form (the last run's
checkpoints and screenshots are under `applications/<APP-ID>/`). Never
retry a `SUBMIT_UNVERIFIED` application — it may already have been
received; ask the user to check first.
