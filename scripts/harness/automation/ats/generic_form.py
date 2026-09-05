"""Generic best-effort form-filler used when no ATS is detected.

Tries a small library of common selectors. Never guesses — if a field
isn't found via a known selector, it's left blank and reported.
"""
from __future__ import annotations
from pathlib import Path

from ..playwright_driver import DriverContext, guarded_action, checkpoint


_SELECTORS: dict[str, list[str]] = {
    "name":     ["input[name*='name' i]:not([name*='user' i])"],
    "first":    ["input[name*='first' i]", "input#first_name"],
    "last":     ["input[name*='last' i]",  "input#last_name"],
    "email":    ["input[type='email']", "input[name*='email' i]"],
    "phone":    ["input[type='tel']",   "input[name*='phone' i]"],
    "linkedin": ["input[name*='linkedin' i]"],
    "github":   ["input[name*='github' i]"],
    "resume":   ["input[type='file'][name*='resume' i]", "input[type='file']"],
}


async def apply(page, ctx: DriverContext, resume_pdf: Path, profile) -> dict:
    await guarded_action(page, lambda: page.goto(ctx.job["job_url"], wait_until="domcontentloaded"), ctx, "goto")
    first, _, last = profile.name.partition(" ")
    filled: dict[str, bool] = {}

    async def _fill(key: str, val: str):
        for sel in _SELECTORS.get(key, []):
            try:
                await guarded_action(page, lambda s=sel, v=val: page.fill(s, v), ctx, f"fill.{key}")
                filled[key] = True
                return
            except Exception:
                continue
        filled[key] = False

    await _fill("name",     profile.name)
    await _fill("first",    first)
    await _fill("last",     last or first)
    await _fill("email",    profile.email)
    await _fill("phone",    profile.phone)
    await _fill("linkedin", profile.linkedin_url)
    await _fill("github",   profile.github_url)

    for sel in _SELECTORS["resume"]:
        try:
            await guarded_action(page, lambda s=sel: page.set_input_files(s, str(resume_pdf)), ctx, "upload_resume")
            filled["resume"] = True
            break
        except Exception:
            continue
    filled.setdefault("resume", False)

    checkpoint(ctx.app_id, "pre_submit", {"url": page.url, "filled": filled})
    return {"ats": "generic", "url": page.url, "filled": filled}
