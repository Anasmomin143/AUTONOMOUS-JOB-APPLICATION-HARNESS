"""Greenhouse: the form is on the job page, in an embedded iframe, or at
the board's embed URL (company slug + job id)."""
from __future__ import annotations
from urllib.parse import parse_qs, urlparse

NAME = "greenhouse"
MANUAL = False


def form_urls(app: dict) -> list[str]:
    url = app.get("job_url") or ""
    urls = [url]
    job_id = app.get("requisition_id") or (parse_qs(urlparse(url).query).get("gh_jid") or [""])[0]
    if app.get("job_source") == "greenhouse" and app.get("company") and job_id:
        urls.append(f"https://boards.greenhouse.io/embed/job_app?for={app['company']}&token={job_id}")
    return urls
