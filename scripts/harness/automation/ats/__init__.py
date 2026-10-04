"""ATS adapters: where each ATS keeps its application form.

The shared form engine (`automation.form`) does the filling; an adapter
only lists candidate form URLs in the order to try them. Adapters with
`MANUAL = True` (Workday, LinkedIn Easy Apply) hand the whole form to the
user: they need accounts and multi-step flows the harness doesn't drive.
"""
from __future__ import annotations
from types import ModuleType

from . import ashby, generic_form, greenhouse, lever, linkedin_easy, workday


def pick_adapter(app: dict) -> ModuleType:
    url = (app.get("job_url") or "").lower()
    source = (app.get("job_source") or "").lower()
    if "myworkdayjobs" in url or "workday" in url:
        return workday
    if "linkedin.com/jobs" in url or source == "linkedin":
        return linkedin_easy
    if source == "greenhouse" or "greenhouse.io" in url or "gh_jid=" in url:
        return greenhouse
    if source == "lever" or "lever.co" in url:
        return lever
    if source == "ashby" or "ashbyhq.com" in url:
        return ashby
    return generic_form
