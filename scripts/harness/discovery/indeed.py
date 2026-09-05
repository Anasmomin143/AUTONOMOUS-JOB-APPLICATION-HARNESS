"""Indeed discovery — Playwright.

Scaffold: Indeed aggressively rate-limits and rotates its selectors.
Enable by setting `discovery.indeed.enabled: true` and providing search
URLs; then implement `_scrape()`.
"""
from __future__ import annotations

from ..config import Config


def fetch(cfg: Config) -> list[dict]:
    cfg_i = (cfg.settings.get("discovery", {}) or {}).get("indeed") or {}
    if not cfg_i.get("enabled"):
        return []
    raise NotImplementedError(
        "Indeed adapter is a scaffold. Set discovery.indeed.enabled=false "
        "for now, or wire up the Playwright scraper in "
        "scripts/harness/discovery/indeed.py."
    )
