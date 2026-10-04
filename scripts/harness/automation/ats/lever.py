"""Lever: jobs.lever.co/<company>/<id> has its form at .../apply."""
from __future__ import annotations

NAME = "lever"
MANUAL = False


def form_urls(app: dict) -> list[str]:
    url = (app.get("job_url") or "").rstrip("/")
    if "jobs.lever.co" in url and not url.endswith("/apply"):
        return [url + "/apply", url]
    return [url]
