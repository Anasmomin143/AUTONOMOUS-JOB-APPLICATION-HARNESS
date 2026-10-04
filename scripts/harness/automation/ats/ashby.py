"""Ashby: jobs.ashbyhq.com/<company>/<id> has its form at .../application."""
from __future__ import annotations

NAME = "ashby"
MANUAL = False


def form_urls(app: dict) -> list[str]:
    url = (app.get("job_url") or "").rstrip("/")
    if "jobs.ashbyhq.com" in url and not url.endswith("/application"):
        return [url + "/application", url]
    return [url]
