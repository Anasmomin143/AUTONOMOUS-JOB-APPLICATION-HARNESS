"""Lever public postings — no auth required.

Endpoint: https://api.lever.co/v0/postings/<slug>?mode=json
"""
from __future__ import annotations
import re

import httpx

from ..config import Config
from .greenhouse import _infer_mode, _extract_stack, get_json


def fetch(cfg: Config, warnings: list[str] | None = None) -> list[dict]:
    slugs: list[str] = list((cfg.settings.get("discovery", {}) or {}).get("lever_slugs") or [])
    out: list[dict] = []
    if not slugs:
        return out
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for slug in slugs:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            data = get_json(client, url, f"lever/{slug}", warnings)
            if not isinstance(data, list):
                continue
            for j in data:
                cats = j.get("categories") or {}
                loc = cats.get("location") or ""
                desc_html = j.get("descriptionPlain") or j.get("description") or ""
                desc = re.sub(r"<[^>]+>", " ", desc_html)
                desc = re.sub(r"\s+", " ", desc).strip()
                out.append({
                    "company":        slug,
                    "role":           j.get("text") or "",
                    "job_url":        j.get("hostedUrl") or j.get("applyUrl") or "",
                    "location":       loc,
                    "work_mode":      cats.get("commitment") or _infer_mode(loc, desc),
                    "posted_date":    j.get("createdAt") or "",
                    "requisition_id": j.get("id") or "",
                    "description":    desc,
                    "tech_stack":     _extract_stack(desc),
                })
    return out
