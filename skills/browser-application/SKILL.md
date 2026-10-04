---
name: browser-application
description: Drive a Playwright browser through an application form for one prepared application. Stops at CAPTCHA/MFA/OTP, and stops before submit for the human approval gate. Per-ATS form locations (Greenhouse, Lever, Ashby, generic; Workday and LinkedIn Easy Apply are manual) with one shared form engine.
---

# browser-application

Entry point: `python -m harness.cli submit --app-id <APP-ID>`, answered
through `python -m harness.cli decide --app-id <APP-ID> <ANSWER>`. The
wrapper protocol is in `.claude/commands/submit.md`.

Backing modules:
- `harness.automation.runner` — the flow, every gate, status updates.
- `harness.automation.form` — field scan, fill + read-back verification,
  submit button, confirmation check.
- `harness.automation.answers` — `messages/screening-answers.yaml`.
- `harness.automation.gate` — pending prompt / decision files with a
  one-time nonce; silence is NO.
- `harness.automation.safety` — visible CAPTCHA/MFA/OTP detector.
- `harness.automation.playwright_driver` — browser session, `state/STOP`,
  checkpoints, screenshots.
- `harness.automation.ats.*` — where each ATS keeps its form.

Never bypass a challenge. Never submit without an explicit YES unless all
three autonomous locks are set (policy mode, allow_application_submission,
and the session confirmation) — `runner` checks them itself.
