"""Append-only human-readable activity log (spec §23)."""
from __future__ import annotations
import datetime as dt

from ..paths import ACTIVITY_LOG


def _ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def log(app_id: str | None, action: str, result: str | None = None) -> None:
    ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    parts = [_ts(), app_id or "-", action]
    if result:
        parts.append(result)
    with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n\n")
