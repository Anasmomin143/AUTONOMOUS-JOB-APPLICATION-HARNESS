---
description: Score every job in jobs/discovered.json.
allowed-tools:
  - Bash(python -m harness.cli score)
  - Read
---

# /score-all

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli score
```

Same behavior as `/score` but processes every job without a `--job`
filter.
