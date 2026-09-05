"""Decide master vs tailored resume (spec §9).

Rule: use MASTER when the score is already ≥ policy.tailor_when_match_below
AND the JD's technology set is a subset of what the master already
emphasizes. Otherwise TAILORED.
"""
from __future__ import annotations

from ..config import Config
from ..profile import ProfileFacts


def decide(job: dict, score_total: int, cfg: Config, profile: ProfileFacts) -> tuple[str, str]:
    """Returns (decision, rationale) where decision is 'master' or 'tailored'."""
    default = str(cfg.policy.get("resume_type_default", "auto")).lower()
    if default in ("master", "tailored"):
        return default, f"Forced by policy resume_type_default={default}"

    threshold = int(cfg.policy.get("tailor_when_match_below", 92))
    if score_total >= threshold:
        # Confirm master already emphasizes the JD's headline skills
        jd_terms = {t.lower() for t in (job.get("tech_stack") or [])}
        profile_terms = {s.lower() for s in profile.skills}
        gap = jd_terms - profile_terms
        if not gap:
            return "master", (
                f"Score {score_total} ≥ {threshold} and no missing tech "
                f"vs master profile."
            )
        return "tailored", (
            f"Score {score_total} ≥ {threshold} but JD emphasizes tech not "
            f"in master profile: {', '.join(sorted(gap))}."
        )
    return "tailored", f"Score {score_total} < {threshold} — tailoring likely to improve alignment."
