"""Playwright browser session, stop sentinel and checkpoints.

Uses the sync Playwright API: the CLI is synchronous and one `submit`
process drives one application. Every step is checkpointed to
`applications/<APP-ID>/checkpoints/<step>.json`, and `state/STOP` is
checked between actions.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path

from ..paths import R, STOP_SENTINEL, app_dir
from . import safety

# Cloud containers ship Chromium here; on a laptop Playwright's own
# download (`python -m playwright install chromium`) is used instead.
_CONTAINER_CHROMIUM = Path("/opt/pw-browsers/chromium")
USER_DATA_DIR = R / ".pw-user-data"


class StopRequested(Exception):
    """/stop was requested; halt before the next action."""


class ChallengeDetected(Exception):
    """CAPTCHA / MFA / OTP on the page — the user must take over."""


def browser_executable() -> str | None:
    """Chromium binary to launch: $HARNESS_CHROMIUM, then the container
    path, else None (Playwright's own install)."""
    env = os.environ.get("HARNESS_CHROMIUM")
    if env:
        return env
    return str(_CONTAINER_CHROMIUM) if _CONTAINER_CHROMIUM.exists() else None


def resolved_browser() -> tuple[str, bool]:
    """(path, exists) of the Chromium `open_browser` will launch."""
    exe = browser_executable()
    if exe is None:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                exe = p.chromium.executable_path
        except Exception as e:
            return f"unresolved ({e!r})", False
    return exe, Path(exe).exists()


def check_stop() -> None:
    if STOP_SENTINEL.exists():
        raise StopRequested("/stop was requested; halting before the next action.")


def check_challenge(page) -> None:
    reason = safety.detect(page)
    if reason:
        raise ChallengeDetected(reason)


def checkpoint(app_id: str, step: str, payload: dict) -> Path:
    d = app_dir(app_id) / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    payload = {"step": step, "at": dt.datetime.now().isoformat(timespec="seconds"), **payload}
    p = d / f"{step}.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def screenshot(page, app_id: str, name: str) -> Path | None:
    d = app_dir(app_id) / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.png"
    try:
        page.screenshot(path=str(p), full_page=True)
        return p
    except Exception:
        return None


def open_browser(headless: bool = False, user_data_dir: Path | None = None):
    """Returns (playwright, context). A persistent profile keeps ATS
    logins between runs; the caller closes both."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        user_data_dir = user_data_dir or USER_DATA_DIR
        user_data_dir.mkdir(parents=True, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            str(user_data_dir), headless=headless, executable_path=browser_executable(),
        )
    except Exception:
        pw.stop()
        raise
    return pw, context
