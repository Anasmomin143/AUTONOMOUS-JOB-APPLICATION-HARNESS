"""LinkedIn discovery — Playwright + user's persistent Chrome profile.

Requires seeding on first run: launch Chromium against
`config/settings.yaml -> discovery.linkedin.user_data_dir`, log in
manually, then re-run `/find-jobs`.

Left as a stub so `discover_all()` reports it cleanly. Fill in
`_scrape()` when you're ready to enable this source (set
`discovery.linkedin.enabled: true` and add `search_urls`).
"""
from __future__ import annotations

from ..config import Config


def fetch(cfg: Config) -> list[dict]:
    li = (cfg.settings.get("discovery", {}) or {}).get("linkedin") or {}
    if not li.get("enabled"):
        return []
    urls = li.get("search_urls") or []
    if not urls:
        raise NotImplementedError(
            "LinkedIn is enabled but `discovery.linkedin.search_urls` is empty. "
            "Add at least one LinkedIn search URL, then re-run."
        )
    raise NotImplementedError(
        "LinkedIn Playwright adapter not yet wired. First run needs you "
        "to log in through the launched Chromium; the selectors change "
        "often, so this ships as a scaffold. See "
        "scripts/harness/discovery/linkedin.py."
    )
