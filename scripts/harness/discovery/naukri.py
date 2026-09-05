"""Naukri discovery — Playwright.

Scaffold: Naukri requires a logged-in session and has strict anti-bot
measures. Seed the persistent user-data dir before enabling.
"""
from __future__ import annotations

from ..config import Config


def fetch(cfg: Config) -> list[dict]:
    cfg_n = (cfg.settings.get("discovery", {}) or {}).get("naukri") or {}
    if not cfg_n.get("enabled"):
        return []
    raise NotImplementedError(
        "Naukri adapter is a scaffold. First-run needs manual login through "
        "the Playwright-controlled browser. See "
        "scripts/harness/discovery/naukri.py."
    )
