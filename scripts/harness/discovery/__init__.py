"""Job discovery adapters.

Public ATS adapters (greenhouse, lever, ashby) are fully implemented and
make live HTTP requests. Login-gated adapters (linkedin, indeed, naukri,
careers_pages) are scaffolded: they raise `NotImplementedError` with a
clear message telling the user what needs to be seeded before the first
run. The dispatcher in `discover_all` catches those and reports them as
"needs setup" rather than crashing the run.
"""
from __future__ import annotations
import datetime as dt
from typing import Callable

from ..config import Config
from ..batch import stable_hash
from . import greenhouse, lever, ashby, linkedin, indeed, naukri, careers_pages


SOURCES: dict[str, Callable[[Config], list[dict]]] = {
    "greenhouse": greenhouse.fetch,
    "lever":      lever.fetch,
    "ashby":      ashby.fetch,
    "linkedin":   linkedin.fetch,
    "indeed":     indeed.fetch,
    "naukri":     naukri.fetch,
    "careers_page": careers_pages.fetch,
}


def normalize_job(source: str, raw: dict) -> dict:
    """Common schema used across the harness."""
    company = raw.get("company") or "?"
    role = raw.get("role") or raw.get("title") or "?"
    url = raw.get("job_url") or raw.get("url") or ""
    req = raw.get("requisition_id") or raw.get("id") or ""
    return {
        "job_hash":        stable_hash(url or f"{company}|{role}|{req}"),
        "source":          source,
        "company":         company,
        "role":            role,
        "job_url":         url,
        "location":        raw.get("location") or "",
        "work_mode":       raw.get("work_mode") or "",
        "experience":      raw.get("experience") or "",
        "salary":          raw.get("salary") or "",
        "posted_date":     raw.get("posted_date") or "",
        "applicant_count": raw.get("applicant_count"),
        "tech_stack":      raw.get("tech_stack") or [],
        "description":     raw.get("description") or "",
        "requisition_id":  req,
        "raw":             raw,
        "discovered_at":   dt.datetime.now().isoformat(timespec="seconds"),
    }


def discover_all(cfg: Config, max_total: int) -> tuple[list[dict], list[str]]:
    """Returns (normalized_jobs, warnings)."""
    collected: list[dict] = []
    warnings: list[str] = []
    per_source_cap = int(cfg.settings.get("discovery", {}).get("max_per_source_per_run", 200))

    for name, fn in SOURCES.items():
        if len(collected) >= max_total:
            break
        try:
            raw = fn(cfg)
        except NotImplementedError as e:
            warnings.append(f"{name}: {e}")
            continue
        except Exception as e:
            warnings.append(f"{name}: unexpected error — {e!r}")
            continue
        for j in raw[:per_source_cap]:
            collected.append(normalize_job(name, j))
            if len(collected) >= max_total:
                break
    return collected, warnings
