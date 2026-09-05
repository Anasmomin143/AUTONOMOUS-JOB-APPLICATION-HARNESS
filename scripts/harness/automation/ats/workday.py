"""Workday apply flow — scaffold.

Workday is multi-page and requires an account. Enable per-tenant selector
overrides here. Ships as a scaffold: it opens the URL, snapshots the
first page, then stops for user takeover.
"""
from __future__ import annotations
from pathlib import Path

from ..playwright_driver import DriverContext, guarded_action, checkpoint


async def apply(page, ctx: DriverContext, resume_pdf: Path, profile) -> dict:
    await guarded_action(page, lambda: page.goto(ctx.job["job_url"], wait_until="domcontentloaded"), ctx, "goto")
    checkpoint(ctx.app_id, "workday.landing", {"url": page.url})
    # Do NOT attempt to sign in — Workday tenants vary. Halt for takeover.
    return {"ats": "workday", "url": page.url, "note": "Workday scaffold — please complete manually."}
