"""Direct company career-page scraper.

For every URL in `config/settings.yaml -> discovery.careers_urls`, fetch
the page and heuristically look for job-title anchors. Enough for a first
pass — for reliable results, add a per-company selector map here.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse

import httpx

from ..config import Config


def fetch(cfg: Config) -> list[dict]:
    urls: list[str] = list((cfg.settings.get("discovery", {}) or {}).get("careers_urls") or [])
    out: list[dict] = []
    if not urls:
        return out
    with httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "job-application-harness/0.1"},
    ) as client:
        for url in urls:
            try:
                r = client.get(url)
                if r.status_code != 200:
                    continue
                out.extend(_extract(url, r.text))
            except httpx.HTTPError:
                continue
    return out


_ANCHOR_RX = re.compile(
    r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.I | re.S,
)
_TITLE_HINTS = re.compile(
    r"(?i)(engineer|developer|frontend|backend|full[- ]?stack|designer|ux|ui)",
)


def _extract(base_url: str, html: str) -> list[dict]:
    company = urlparse(base_url).netloc.split(".")[-2] or "unknown"
    seen: set[str] = set()
    out: list[dict] = []
    for m in _ANCHOR_RX.finditer(html):
        href, txt = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        txt = re.sub(r"\s+", " ", txt).strip()
        if not txt or not _TITLE_HINTS.search(txt):
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        out.append({
            "company":     company,
            "role":        txt[:120],
            "job_url":     full,
            "location":    "",
            "description": "",
        })
    return out
