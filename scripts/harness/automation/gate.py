"""Human approval gate (spec §14).

The `submit` process opens a prompt — `applications/<APP-ID>/pending_approval.json`
with a stage and a fresh nonce — prints a `HARNESS_REQUEST:` line, and
waits. The user's answer arrives through `harness decide`, which writes
`decision.json` carrying the same nonce. A decision only counts for the
prompt it answers, so a stale YES can never approve a later form.
Silence (timeout) is NO.
"""
from __future__ import annotations
import datetime as dt
import json
import secrets
import time

from ..paths import app_dir
from ..state import read_json, write_json
from .playwright_driver import check_stop

# stage -> answers it accepts
STAGES: dict[str, tuple[str, ...]] = {
    "approval": ("YES", "NO"),       # submit this filled form?
    "input":    ("CONTINUE", "NO"),  # unanswered questions
    "takeover": ("CONTINUE", "NO"),  # CAPTCHA / manual step in the browser
}


def pending_path(app_id: str):
    return app_dir(app_id) / "pending_approval.json"


def decision_path(app_id: str):
    return app_dir(app_id) / "decision.json"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def open_prompt(app_id: str, stage: str, payload: dict | None = None) -> str:
    """Write the pending prompt, announce it, return its nonce."""
    nonce = secrets.token_hex(8)
    decision_path(app_id).unlink(missing_ok=True)
    write_json(pending_path(app_id), {
        "app_id": app_id, "stage": stage, "nonce": nonce,
        "accepts": list(STAGES[stage]), "at": _now(), **(payload or {}),
    })
    request = {"app_id": app_id, "stage": stage, "nonce": nonce, "accepts": list(STAGES[stage])}
    print(f"HARNESS_REQUEST: {stage} {json.dumps(request)}", flush=True)
    return nonce


def close_prompt(app_id: str) -> None:
    pending_path(app_id).unlink(missing_ok=True)
    decision_path(app_id).unlink(missing_ok=True)


def wait(app_id: str, nonce: str, timeout: float, poll: float = 1.0) -> str | None:
    """The decision for this prompt, or None if none arrives in time.
    Raises StopRequested if /stop is called while waiting."""
    pending = read_json(pending_path(app_id), {})
    accepts = set(pending.get("accepts") or ())
    deadline = time.monotonic() + timeout
    while True:
        check_stop()
        d = read_json(decision_path(app_id), {})
        if d.get("nonce") == nonce and d.get("decision") in accepts:
            return d["decision"]
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll)


def decide(app_id: str, decision: str) -> tuple[bool, str]:
    """Record the user's answer to the prompt currently open for `app_id`."""
    pending = read_json(pending_path(app_id), {})
    if not pending.get("nonce"):
        return False, f"No prompt is waiting for {app_id}."
    decision = decision.strip().upper()
    accepts = tuple(pending.get("accepts") or ())
    if decision not in accepts:
        return False, f"The {pending.get('stage')} prompt for {app_id} accepts {' / '.join(accepts)}, not {decision!r}."
    write_json(decision_path(app_id), {
        "app_id": app_id, "decision": decision, "nonce": pending["nonce"],
        "stage": pending.get("stage"), "at": _now(),
    })
    return True, f"Recorded {decision} for {app_id} ({pending.get('stage')})."
