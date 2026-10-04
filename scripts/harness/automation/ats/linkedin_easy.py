"""LinkedIn Easy Apply: requires your logged-in LinkedIn session. Manual:
the harness opens the job, the user completes and submits it, and the
harness verifies the confirmation."""
from __future__ import annotations

NAME = "linkedin"
MANUAL = True
REASON = "LinkedIn Easy Apply runs inside your logged-in LinkedIn session."


def form_urls(app: dict) -> list[str]:
    return [app.get("job_url") or ""]
