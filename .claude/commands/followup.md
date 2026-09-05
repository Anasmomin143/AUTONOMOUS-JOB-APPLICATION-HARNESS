---
description: Draft follow-ups for applications past the follow-up window.
allowed-tools:
  - Bash(python -m harness.cli followup)
  - Bash(python -m harness.cli sync *)
  - mcp__Gmail__search_threads
  - mcp__Gmail__create_draft
  - mcp__Gmail__list_drafts
  - Read
  - Write
---

# /followup

Always run `/sync` first (or the equivalent Gmail search) so status is
current. Then:

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli followup
```

For each due application (7 days after apply for the first, +7-10 for
the second, hard cap 2 unanswered):

1. Confirm no recruiter reply exists (Gmail search on company domain +
   role + application ID).
2. Draft a personalized, short message using only verified information
   from `profile/master-profile.md` and existing thread history.
3. Save via `mcp__Gmail__create_draft`.
4. Present each draft to the user. DO NOT SEND without explicit YES,
   even if `automation-policy.yaml` has `allow_followups: true` — the
   spec §14 puts follow-ups on the always-approval list.
