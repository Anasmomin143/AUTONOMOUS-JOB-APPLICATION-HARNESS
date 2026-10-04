"""Hard filters (settings.yaml `filters:` + automation-policy allow-lists).

A job that fails any filter is rejected regardless of its match score.
Applied at discovery (so off-target postings never use up the count) and
again at scoring (so jobs discovered under older rules are re-checked).
"""
from __future__ import annotations
import re

from .config import Config
from .scoring import extract_required_years


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def reasons(job: dict, cfg: Config) -> list[str]:
    """Every reason `job` must be rejected; empty when it passes."""
    f = cfg.settings.get("filters") or {}
    role = str(job.get("role") or "")
    company = str(job.get("company") or "")
    location = str(job.get("location") or "")
    out: list[str] = []

    for rx in f.get("title_blocklist") or []:
        if re.search(rx, role):
            out.append(f"title matches title_blocklist {rx!r}")
            break

    targets = f.get("target_role_patterns") or []
    if targets and not _matches_any(targets, role):
        out.append("title matches no filters.target_role_patterns")

    allowed_roles = cfg.policy.get("allowed_roles") or []
    if allowed_roles and not _matches_any(allowed_roles, role):
        out.append("title matches no policy allowed_roles")

    # An empty location is unknown, not disqualifying.
    allowed_locations = cfg.policy.get("allowed_locations") or []
    if location and allowed_locations and not _matches_any(allowed_locations, location):
        out.append(f"location {location!r} matches no policy allowed_locations")

    blocked = {str(c).lower() for c in f.get("company_blocklist") or []}
    if company.lower() in blocked:
        out.append(f"company {company!r} is on company_blocklist")

    max_years = f.get("max_experience_years")
    needed = extract_required_years(f"{role}\n{job.get('description') or ''}")
    if max_years is not None and needed is not None and needed > int(max_years):
        out.append(f"requires {needed}+ years (max_experience_years={max_years})")

    return out
