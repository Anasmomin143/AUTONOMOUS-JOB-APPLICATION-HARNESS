"""Supervised / autonomous mode transitions (spec §14).

Autonomous mode has **two locks**:

  1. `config/automation-policy.yaml` must have BOTH
     `mode: autonomous` and `allow_application_submission: true`.
  2. The user must explicitly confirm via /mode autonomous, which
     writes a session token to `state/mode.json` after two-step YES.

Any missing lock forces the supervised approval gate.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass

from .config import Config
from .paths import MODE_LOG, MODE_STATE
from .state import read_json, write_json


@dataclass
class ModeStatus:
    effective: str          # "supervised" | "autonomous"
    policy_mode: str
    submission_allowed: bool
    session_confirmed: bool
    daily_used: int
    daily_limit: int


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def status(cfg: Config, daily_used: int = 0) -> ModeStatus:
    st = read_json(MODE_STATE, {})
    session_confirmed = bool(st.get("session_autonomous_confirmed"))
    effective = "autonomous" if (
        cfg.mode == "autonomous"
        and cfg.submission_allowed
        and session_confirmed
    ) else "supervised"
    return ModeStatus(
        effective=effective,
        policy_mode=cfg.mode,
        submission_allowed=cfg.submission_allowed,
        session_confirmed=session_confirmed,
        daily_used=daily_used,
        daily_limit=cfg.max_per_day,
    )


def log_mode_change(prev: str, new: str, user_confirmation: str, extras: dict | None = None) -> None:
    MODE_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"\n{_now()}\nMODE_CHANGED\n{prev} → {new}\n"
        f"User confirmation: {user_confirmation}\n"
    )
    for k, v in (extras or {}).items():
        line += f"{k}: {v}\n"
    with MODE_LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def set_supervised() -> None:
    prev = read_json(MODE_STATE, {}).get("effective", "supervised")
    write_json(MODE_STATE, {"effective": "supervised", "session_autonomous_confirmed": False})
    log_mode_change(prev, "supervised", "N/A")


def confirm_session_autonomous() -> None:
    prev = read_json(MODE_STATE, {}).get("effective", "supervised")
    write_json(MODE_STATE, {"effective": "autonomous", "session_autonomous_confirmed": True, "confirmed_at": _now()})
    log_mode_change(prev, "autonomous", "YES (two-step)")
