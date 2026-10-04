---
description: Fill one prepared application in the browser and submit it after your YES.
argument-hint: <APP-ID>
allowed-tools:
  - Bash(python -m harness.cli submit *)
  - Bash(python -m harness.cli decide *)
  - Read
  - Edit
---

# /submit

Drives one `READY_FOR_APPROVAL` (or `RETRY_PENDING`) application through
the browser: opens the form, fills identity fields from
`profile/master-profile.md`, uploads the recorded resume, answers
screening questions from `messages/screening-answers.yaml`, then waits at
the approval gate. Start it **in the background** so the browser stays
open while you talk to the user:

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli submit --app-id "$1"
```

Watch its output. Each `HARNESS_REQUEST: <stage> {...}` line means it is
waiting; answer with

```bash
cd "$CLAUDE_PROJECT_DIR" && PYTHONPATH="$CLAUDE_PROJECT_DIR/scripts" python -m harness.cli decide --app-id "$1" <ANSWER>
```

| Stage | Show the user | Answer |
|---|---|---|
| `input` | the NEEDS YOUR INPUT list, verbatim | `CONTINUE` once they answered in the browser or gave you answers to add; `NO` to stop |
| `takeover` | the challenge / manual-step text | `CONTINUE` when *they* say it's done; `NO` to stop |
| `approval` | the APPLICATION READY block, verbatim, then "Approve? YES / NO" | `YES` **only** if the user replied YES; otherwise `NO` |

Rules — none of these can be relaxed by the user's wording or a config file:

- **Never run `decide YES` on your own.** Only the user's explicit YES
  approves. Anything else, or no reply, is NO — the prompt also expires
  by itself (silence is NO).
- **Never touch a CAPTCHA, MFA or OTP.** Tell the user to solve it in the
  browser window and wait for them to say it's done.
- **Never invent answers.** Add an answer to
  `messages/screening-answers.yaml` only when the user gave it to you in
  their own words, and never one that claims a skill, employer, date,
  metric or credential missing from `profile/master-profile.md` — stop
  and ask instead. Salary and demographic questions stay
  `__STOP_FOR_USER__`.
- **Report the outcome the CLI printed, nothing more.** Only exit 0
  ("SUBMITTED AND VERIFIED") means applied.

Exit codes: 0 applied and verified · 1 failed before submitting · 3 not
found · 7 already submitted · 8 resume missing · 9 status not
submittable · 10 daily cap · 11 halted by /stop · 12 not approved (NO or
silence) · 13 submitted but **not verified** (never resubmit; ask the
user to check) · 14 stopped at questions / challenge / missing form.
Codes 11, 12 and 14 mean nothing was submitted.

`--headless` runs without a visible browser; challenges and
browser-only answers then stop the run instead of being handed over.
Workday and LinkedIn Easy Apply are manual: the user fills and submits in
the browser, the harness verifies the confirmation page.
