"""Greenhouse public job board — no auth required.

Endpoint: https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true
"""
from __future__ import annotations
import re

import httpx

from ..config import Config


def fetch(cfg: Config) -> list[dict]:
    slugs: list[str] = list((cfg.settings.get("discovery", {}) or {}).get("greenhouse_slugs") or [])
    out: list[dict] = []
    if not slugs:
        return out
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for slug in slugs:
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
            r = client.get(url)
            if r.status_code != 200:
                continue
            data = r.json()
            for j in data.get("jobs", []):
                loc = (j.get("location") or {}).get("name", "")
                desc_html = j.get("content") or ""
                desc = re.sub(r"<[^>]+>", " ", desc_html)
                desc = re.sub(r"\s+", " ", desc).strip()
                out.append({
                    "company":        slug,
                    "role":           j.get("title") or "",
                    "job_url":        j.get("absolute_url") or "",
                    "location":       loc,
                    "work_mode":      _infer_mode(loc, desc),
                    "posted_date":    j.get("updated_at") or j.get("first_published") or "",
                    "requisition_id": str(j.get("id") or ""),
                    "description":    desc,
                    "tech_stack":     _extract_stack(desc),
                })
    return out


_MODE_RX = {
    "remote": re.compile(r"\bremote\b", re.I),
    "hybrid": re.compile(r"\bhybrid\b", re.I),
    "onsite": re.compile(r"\bon[- ]?site|\bin[- ]office", re.I),
}


def _infer_mode(location: str, desc: str) -> str:
    blob = f"{location}\n{desc}"
    for mode, rx in _MODE_RX.items():
        if rx.search(blob):
            return mode
    return ""


_KNOWN_TECH = [
    "React", "Next.js", "Angular", "Vue", "TypeScript", "JavaScript",
    "Redux", "Zustand", "RxJS", "NgRx", "Tailwind", "SCSS", "Sass",
    "GraphQL", "REST", "Node.js", "Express", "MongoDB", "Postgres",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Playwright", "Jest",
    "Cypress", "Storybook", "Webpack", "Vite",
]


def _extract_stack(desc: str) -> list[str]:
    found: list[str] = []
    for t in _KNOWN_TECH:
        if re.search(rf"\b{re.escape(t)}\b", desc, re.I):
            found.append(t)
    return found
