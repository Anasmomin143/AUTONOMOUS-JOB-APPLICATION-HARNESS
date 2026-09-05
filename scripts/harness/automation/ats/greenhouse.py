"""Greenhouse-hosted apply flow.

Fills the standard first_name/last_name/email/phone fields and uploads
the tailored resume. Stops at the submit button and hands off to the
approval gate.
"""
from __future__ import annotations
from pathlib import Path

from ..playwright_driver import DriverContext, guarded_action, checkpoint


async def apply(page, ctx: DriverContext, resume_pdf: Path, profile) -> dict:
    await guarded_action(page, lambda: page.goto(ctx.job["job_url"], wait_until="domcontentloaded"), ctx, "goto")

    # First / last name
    first, _, last = profile.name.partition(" ")
    for sel, val in [
        ("input#first_name",   first),
        ("input#last_name",    last or first),
        ("input#email",        profile.email),
        ("input#phone",        profile.phone),
    ]:
        try:
            await guarded_action(page, lambda s=sel, v=val: page.fill(s, v), ctx, f"fill.{sel}")
        except Exception:
            continue

    # Resume upload
    for sel in ("input#resume", "input[type='file'][name*='resume' i]"):
        try:
            await guarded_action(page, lambda s=sel: page.set_input_files(s, str(resume_pdf)), ctx, "upload_resume")
            break
        except Exception:
            continue

    # LinkedIn / website
    for sel, val in [
        ("input[name*='linkedin' i]", profile.linkedin_url),
        ("input[name*='github' i]",   profile.github_url),
        ("input[name*='website' i]",  profile.linkedin_url),
    ]:
        try:
            await guarded_action(page, lambda s=sel, v=val: page.fill(s, v), ctx, f"fill.{sel}")
        except Exception:
            continue

    # Snapshot pre-submit
    dom = await page.content()
    checkpoint(ctx.app_id, "pre_submit", {"url": page.url, "dom_len": len(dom)})
    try:
        shot = str((await page.screenshot()).hex()[:64])
    except Exception:
        shot = ""
    return {"ats": "greenhouse", "url": page.url, "screenshot_hex_prefix": shot}
