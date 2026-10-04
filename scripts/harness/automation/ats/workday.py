"""Workday: account sign-in and multi-page tenant-specific flows. Manual:
the harness opens the job, the user completes and submits it, and the
harness verifies the confirmation."""
from __future__ import annotations

NAME = "workday"
MANUAL = True
REASON = "Workday needs a tenant account and a multi-page flow the harness doesn't drive."


def form_urls(app: dict) -> list[str]:
    return [app.get("job_url") or ""]
