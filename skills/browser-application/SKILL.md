---
name: browser-application
description: Drive a Playwright browser through an application form for one prepared application. Stops at CAPTCHA/MFA/OTP, and stops before submit for the human approval gate. Uses per-ATS adapters (Greenhouse, Lever, Workday scaffold, LinkedIn Easy Apply scaffold, generic fallback).
---

# browser-application

Backing modules:
- `harness.automation.playwright_driver` — session + checkpoint + stop sentinel.
- `harness.automation.safety` — CAPTCHA/MFA/OTP detector.
- `harness.automation.ats.*` — one per ATS; `pick_adapter(url)` chooses.

Never bypass a challenge. Never submit without an explicit YES unless
autonomous mode's two locks are satisfied (config + session), which the
CLI enforces server-side.
