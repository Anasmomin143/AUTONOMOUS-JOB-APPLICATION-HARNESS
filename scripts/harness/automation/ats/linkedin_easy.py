"""LinkedIn Easy Apply — scaffold.

Requires the LinkedIn user-data dir seeded with a logged-in session.
Ships as a scaffold: opens the job and stops for user takeover.
"""
from __future__ import annotations
from pathlib import Path

from ..playwright_driver import DriverContext, guarded_action, checkpoint


async def apply(page, ctx: DriverContext, resume_pdf: Path, profile) -> dict:
    await guarded_action(page, lambda: page.goto(ctx.job["job_url"], wait_until="domcontentloaded"), ctx, "goto")
    checkpoint(ctx.app_id, "linkedin.landing", {"url": page.url})
    return {"ats": "linkedin", "url": page.url, "note": "LinkedIn Easy Apply scaffold — please complete manually."}
