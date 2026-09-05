"""Ashby public postings — no auth required.

Endpoint: https://api.ashbyhq.com/posting-api/job-board/<slug>?includeCompensation=true
"""
from __future__ import annotations
import re

import httpx

from ..config import Config
from .greenhouse import _infer_mode, _extract_stack


def fetch(cfg: Config) -> list[dict]:
    slugs: list[str] = list((cfg.settings.get("discovery", {}) or {}).get("ashby_slugs") or [])
    out: list[dict] = []
    if not slugs:
        return out
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for slug in slugs:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
            r = client.get(url)
            if r.status_code != 200:
                continue
            data = r.json()
            for j in data.get("jobs", []):
                loc = j.get("location") or ""
                desc = j.get("descriptionPlain") or ""
                if not desc:
                    desc_html = j.get("descriptionHtml") or ""
                    desc = re.sub(r"<[^>]+>", " ", desc_html)
                desc = re.sub(r"\s+", " ", desc).strip()
                out.append({
                    "company":        slug,
                    "role":           j.get("title") or "",
                    "job_url":        j.get("jobUrl") or j.get("applyUrl") or "",
                    "location":       loc,
                    "work_mode":      j.get("employmentType") or _infer_mode(loc, desc),
                    "posted_date":    j.get("publishedAt") or "",
                    "requisition_id": j.get("id") or "",
                    "description":    desc,
                    "tech_stack":     _extract_stack(desc),
                })
    return out
