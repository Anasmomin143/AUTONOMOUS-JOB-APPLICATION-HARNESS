---
description: Show or change the autonomy mode (supervised / autonomous / status).
argument-hint: supervised | autonomous | status
allowed-tools:
  - Bash(python -m harness.cli mode *)
  - Read
---

# /mode

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli mode "${1:-status}" ${YES:+--confirm YES}
```

Autonomous mode has two locks (both required):

1. `config/automation-policy.yaml` must have `mode: autonomous` AND
   `allow_application_submission: true`. Ask the user to edit the file
   before running `/mode autonomous`.
2. Session confirmation: the first `/mode autonomous` prints the safety
   warning; a second run with `YES=YES /mode autonomous` sets the
   session flag.

Interview acceptance and offer acceptance are hard-coded off and
CANNOT be enabled by config or by any slash-command flag.
