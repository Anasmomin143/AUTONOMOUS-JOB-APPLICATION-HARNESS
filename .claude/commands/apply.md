---
description: Batch-prepare and (with approval) submit N applications.
argument-hint: <count> [random] [--score N] [--role "..."] [--location "..."]
allowed-tools:
  - Bash(python -m harness.cli apply *)
  - Bash(python -m harness.cli mode status)
  - Read
  - Write
---

# /apply

Batch flow (spec §12–14):

1. Filter qualified jobs by score / role / location / de-duplication.
2. Select `<count>` (top-scoring, or diversified-random when `random` given).
3. For each: run the full `prepare` pipeline. Never submits.
4. Print the batch summary.
5. Then, for each application in the batch, hand off to the browser
   automation loop:
   - open the job URL in Playwright,
   - fill the form via the ATS adapter (Greenhouse/Lever/Workday/LinkedIn/generic),
   - upload the correct resume,
   - snapshot state,
   - PRINT the "APPLICATION READY" block,
   - WAIT for the user's YES/NO,
   - submit only on YES,
   - verify submission, update tracker, log activity,
   - schedule the first follow-up date.

**Silence is NO.** Never auto-submit unless `/mode autonomous` has been
confirmed AND `automation-policy.yaml` allows submission — the Python
CLI already enforces this; do not attempt to bypass it.

Bash for the batch prep:

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli apply \
  --count "${1:-1}" \
  $([[ "$2" == "random" ]] && echo "--random") \
  ${SCORE:+--score $SCORE} \
  ${ROLE:+--role "$ROLE"} \
  ${LOCATION:+--location "$LOCATION"}
```

Then walk each prepared application through the browser gate using
the Playwright driver in `scripts/harness/automation/playwright_driver.py`.
