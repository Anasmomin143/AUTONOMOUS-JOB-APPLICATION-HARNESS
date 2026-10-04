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
5. Then submit the prepared applications **one at a time** with the
   `/submit <APP-ID>` flow (see `.claude/commands/submit.md`): it fills
   the form, prints the APPLICATION READY block, waits for the user's
   YES/NO, submits only on YES, verifies the confirmation page, updates
   the tracker and schedules the first follow-up.

**Silence is NO.** `harness submit` skips the YES prompt only when all
three autonomous locks are set (policy `mode: autonomous`,
`allow_application_submission: true`, and the `/mode autonomous` YES
confirmation); it enforces this itself. Never bypass it.

Bash for the batch prep:

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli apply \
  --count "${1:-1}" \
  $([[ "$2" == "random" ]] && echo "--random") \
  ${SCORE:+--score $SCORE} \
  ${ROLE:+--role "$ROLE"} \
  ${LOCATION:+--location "$LOCATION"}
```

Then run `/submit <APP-ID>` for each application the batch prepared.
