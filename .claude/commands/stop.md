---
description: Halt automation at the next boundary.
allowed-tools:
  - Bash(python -m harness.cli stop)
---

# /stop

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli stop
```

Writes `state/STOP`. The Playwright driver checks for this file between
every action; the next action refuses to run. Delete the sentinel (or
run `/stop --clear` in a future version) to allow work to resume.
