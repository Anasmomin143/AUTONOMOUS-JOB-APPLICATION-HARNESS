"""Playwright driver + approval gate.

Uses the pre-installed Chromium at /opt/pw-browsers/chromium (see env in
.claude/settings.json). Every action is checkpointed to
`applications/<APP-ID>/checkpoints/<step>.json`. Between actions, the
driver checks for `state/STOP` and halts cleanly.
"""
from __future__ import annotations
import asyncio
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from ..paths import STOP_SENTINEL, app_dir
from . import safety


@dataclass
class DriverContext:
    app_id: str
    job: dict
    headless: bool = False


class StopRequested(Exception):
    """Raised when /stop was called between actions."""


class ChallengeDetected(Exception):
    """CAPTCHA/MFA/OTP — user takeover required."""


def _check_stop() -> None:
    if STOP_SENTINEL.exists():
        raise StopRequested("/stop was requested; halting before next action.")


def checkpoint(app_id: str, step: str, payload: dict) -> Path:
    d = app_dir(app_id) / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    payload = {"step": step, "at": dt.datetime.now().isoformat(timespec="seconds"), **payload}
    p = d / f"{step}.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


async def open_browser(user_data_dir: Path | None = None, headless: bool = False):
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    if user_data_dir:
        user_data_dir.mkdir(parents=True, exist_ok=True)
        context = await p.chromium.launch_persistent_context(
            str(user_data_dir), headless=headless,
            executable_path="/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None,
        )
    else:
        browser = await p.chromium.launch(headless=headless,
            executable_path="/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
        context = await browser.new_context()
    return p, context


async def new_page(context):
    return await context.new_page()


async def guarded_action(page, coro_factory, ctx: DriverContext, step: str):
    _check_stop()
    reason = await safety.detect(page)
    if reason:
        checkpoint(ctx.app_id, f"halt.{step}", {"reason": reason, "url": page.url})
        raise ChallengeDetected(reason)
    result = await coro_factory()
    _check_stop()
    return result


def print_approval_block(app_id: str, job: dict, resume_type: str, resume_file: str, screening_count: int) -> None:
    print("\nAPPLICATION READY")
    print(f"Application: {app_id}")
    print(f"Company: {job.get('company')}")
    print(f"Role: {job.get('role')}")
    print(f"Match: {job.get('match_score')}%")
    print(f"Resume: {resume_type.upper()}")
    print(f"Resume file: {resume_file}")
    print(f"Screening questions: {screening_count}")
    print("All answers verified.")
    print("Ready to submit.")
    print("Approve? YES / NO")


def write_pending_approval(app_id: str, job: dict, resume_file: str, screening: list[dict]) -> Path:
    p = app_dir(app_id) / "pending_approval.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "app_id": app_id,
        "job": job,
        "resume_file": resume_file,
        "screening_answers": screening,
        "at": dt.datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def read_decision(app_id: str) -> str | None:
    p = app_dir(app_id) / "decision.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("decision")
    except Exception:
        return None


# Convenience sync wrappers so the CLI (which is sync) can call async code.

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if not asyncio.get_event_loop().is_running() \
        else asyncio.ensure_future(coro)
