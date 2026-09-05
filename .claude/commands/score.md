---
description: Score one job by ID, or all discovered jobs when no ID given.
argument-hint: [job-id]
allowed-tools:
  - Bash(python -m harness.cli score *)
  - Read
---

# /score

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli score ${1:+--job "$1"}
```

Applies the weights from `config/scoring.yaml`. Writes per-job:

- `match_score` (0-100)
- `score_breakdown` (per-category)
- `score_rationale` (matched / missing / experience delta)
- `classification` (strong | review | low | reject)

Jobs scoring ≥ `thresholds.low` move to `jobs/qualified.json`; the rest
move to `jobs/rejected.json`. Report totals to the user.
