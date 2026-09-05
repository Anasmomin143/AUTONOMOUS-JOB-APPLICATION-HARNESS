---
description: Discover up to N jobs from the sources configured in settings.yaml.
argument-hint: <count>
allowed-tools:
  - Bash(python -m harness.cli discover *)
  - Read
---

# /find-jobs

Discovers jobs from the enabled sources and appends new ones to
`jobs/discovered.json` (deduping against archive + already-seen).

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli discover --count "${1:-100}"
```

Working:  Greenhouse / Lever / Ashby public boards.
Scaffold: LinkedIn / Indeed / Naukri / career-pages (fill in the
adapter in `scripts/harness/discovery/*.py` before enabling in
`config/settings.yaml`).

After running, show the user the new count and any warnings. Do NOT
score or apply — those are separate commands.
