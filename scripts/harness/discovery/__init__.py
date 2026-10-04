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

from .. import filters
from ..config import Config
from ..batch import stable_hash
from . import greenhouse, lever, ashby, linkedin, indeed, naukri, careers_pages


# Each fetcher takes (cfg, warnings) and appends per-company problems to
# `warnings` instead of letting one bad slug abort the whole source.
SOURCES: dict[str, Callable[[Config, list[str]], list[dict]]] = {
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


def discover_all(
    cfg: Config, max_total: int, seen: set[str] | None = None,
) -> tuple[list[dict], list[str], dict[str, int]]:
    """Returns (new_jobs, warnings, skipped_counts).

    Jobs already in `seen` (job hashes / URLs) and jobs failing the hard
    filters are skipped *before* counting toward `max_total` and the
    per-source cap, so a run returns up to N new, on-target jobs.
    """
    seen = set(seen or ())
    collected: list[dict] = []
    warnings: list[str] = []
    skipped = {"duplicate": 0, "filtered": 0}
    per_source_cap = int(cfg.settings.get("discovery", {}).get("max_per_source_per_run", 200))

    for name, fn in SOURCES.items():
        if len(collected) >= max_total:
            break
        try:
            raw = fn(cfg, warnings)
        except NotImplementedError as e:
            warnings.append(f"{name}: {e}")
            continue
        except Exception as e:
            warnings.append(f"{name}: unexpected error — {e!r}")
            continue
        taken = 0
        for j in raw:
            job = normalize_job(name, j)
            if job["job_hash"] in seen or (job["job_url"] and job["job_url"] in seen):
                skipped["duplicate"] += 1
                continue
            if filters.reasons(job, cfg):
                skipped["filtered"] += 1
                continue
            seen.update({job["job_hash"], job["job_url"]})
            collected.append(job)
            taken += 1
            if taken >= per_source_cap or len(collected) >= max_total:
                break
    return collected, warnings, skipped
