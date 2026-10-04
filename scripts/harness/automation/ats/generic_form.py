"""Any other careers site: start at the job URL; the runner follows an
embedded ATS iframe or an "Apply" button if the form isn't there."""
from __future__ import annotations

NAME = "generic"
MANUAL = False


def form_urls(app: dict) -> list[str]:
    return [app.get("job_url") or ""]
