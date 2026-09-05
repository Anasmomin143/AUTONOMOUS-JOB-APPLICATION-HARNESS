"""Lever-hosted apply flow."""
from __future__ import annotations
from pathlib import Path

from ..playwright_driver import DriverContext, guarded_action, checkpoint


async def apply(page, ctx: DriverContext, resume_pdf: Path, profile) -> dict:
    await guarded_action(page, lambda: page.goto(ctx.job["job_url"], wait_until="domcontentloaded"), ctx, "goto")

    for sel, val in [
        ("input[name='name']",     profile.name),
        ("input[name='email']",    profile.email),
        ("input[name='phone']",    profile.phone),
        ("input[name*='linkedin' i]", profile.linkedin_url),
        ("input[name*='github' i]",   profile.github_url),
    ]:
        try:
            await guarded_action(page, lambda s=sel, v=val: page.fill(s, v), ctx, f"fill.{sel}")
        except Exception:
            continue

    try:
        await guarded_action(
            page,
            lambda: page.set_input_files("input[type='file']", str(resume_pdf)),
            ctx, "upload_resume",
        )
    except Exception:
        pass

    checkpoint(ctx.app_id, "pre_submit", {"url": page.url})
    return {"ats": "lever", "url": page.url}
