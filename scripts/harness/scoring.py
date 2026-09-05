"""Job match scoring (spec §5)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

from .config import Config
from .profile import ProfileFacts


@dataclass
class Score:
    total: int
    breakdown: dict[str, int]
    matched: dict[str, list[str]]
    missing: dict[str, list[str]]
    classification: str      # strong | review | low | reject
    rationale: str


def classify(total: int, thresholds: dict) -> str:
    if total >= thresholds.get("strong", 90):
        return "strong"
    if total >= thresholds.get("review", 80):
        return "review"
    if total >= thresholds.get("low", 70):
        return "low"
    return "reject"


def _find_all(text: str, needles: list[str]) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for n in needles:
        if not n:
            continue
        if re.search(rf"\b{re.escape(n.lower())}\b", lowered):
            found.append(n)
    return found


def score_job(job: dict, cfg: Config, profile: ProfileFacts) -> Score:
    weights: dict[str, int] = cfg.scoring.get("weights") or {}
    thresholds: dict[str, int] = cfg.scoring.get("thresholds") or {}
    syns: dict[str, list[str]] = cfg.scoring.get("skill_synonyms") or {}
    domains: dict[str, list[str]] = cfg.scoring.get("domains") or {}

    jd = " ".join(str(v) for v in (job.get("role"), job.get("description"), " ".join(job.get("tech_stack") or []))).lower()

    # ---- Technical skills ----
    profile_skills_lc = [s.lower() for s in profile.skills]
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    all_terms: list[str] = []
    for canonical, aliases in syns.items():
        all_terms.extend(aliases)
    # Which of the JD's mentioned tech does the profile cover?
    jd_tech = _find_all(jd, list({t for group in syns.values() for t in group}))
    for t in jd_tech:
        canonical = _canonicalize(t, syns)
        if any(a.lower() in profile_skills_lc for a in syns.get(canonical, [canonical])):
            if canonical not in matched_skills:
                matched_skills.append(canonical)
        else:
            if canonical not in missing_skills:
                missing_skills.append(canonical)
    tech_score = _weighted_ratio(matched_skills, matched_skills + missing_skills, weights.get("technical_skills", 30))

    # ---- Relevant experience ----
    yoe_needed = _extract_years(jd)
    yoe_have = profile.total_years_experience
    if yoe_needed is None:
        exp_score = weights.get("relevant_experience", 25)  # unknown → give full
    else:
        ratio = min(yoe_have / max(yoe_needed, 1), 1.0)
        exp_score = int(round(ratio * weights.get("relevant_experience", 25)))

    # ---- Responsibilities ----
    resp_hits = _find_all(jd, [
        "component library", "design system", "code reviews", "code splitting",
        "lazy loading", "accessibility", "wcag", "ssr", "server-side rendering",
        "state management", "ci/cd", "unit tests", "e2e", "playwright", "jest",
    ])
    resp_score = _weighted_ratio(resp_hits, resp_hits + ["_min1"], weights.get("responsibilities", 20))

    # ---- Domain ----
    domain_matched = []
    for dom, terms in domains.items():
        if _find_all(jd, terms) and dom in profile.domains:
            domain_matched.append(dom)
    domain_score = weights.get("domain_experience", 10) if domain_matched else int(weights.get("domain_experience", 10) * 0.4)

    # ---- Seniority ----
    seniority_score = _seniority_match(jd, profile, weights.get("seniority", 5))

    # ---- ATS keyword alignment (proxy: unique skills hit) ----
    ats_score = _weighted_ratio(matched_skills, matched_skills + missing_skills, weights.get("ats_keyword_alignment", 5))

    # ---- Education / other ----
    edu_score = weights.get("education_and_other", 5)  # neutral by default

    total = tech_score + exp_score + resp_score + domain_score + seniority_score + ats_score + edu_score
    total = max(0, min(100, total))

    breakdown = {
        "technical_skills":      tech_score,
        "relevant_experience":   exp_score,
        "responsibilities":      resp_score,
        "domain_experience":     domain_score,
        "seniority":             seniority_score,
        "ats_keyword_alignment": ats_score,
        "education_and_other":   edu_score,
    }
    matched = {
        "skills":         matched_skills,
        "responsibilities": resp_hits,
        "domains":        domain_matched,
    }
    missing = {"skills": missing_skills}

    rationale = _rationale(matched, missing, yoe_have, yoe_needed)
    return Score(total, breakdown, matched, missing, classify(total, thresholds), rationale)


def _canonicalize(term: str, syns: dict[str, list[str]]) -> str:
    tl = term.lower()
    for canonical, aliases in syns.items():
        if tl in [a.lower() for a in aliases] or tl == canonical.lower():
            return canonical
    return tl


def _weighted_ratio(hits: list[Any], universe: list[Any], weight: int) -> int:
    if not universe:
        return weight
    return int(round(min(1.0, len(hits) / len(universe)) * weight))


def _extract_years(text: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", text)
    return int(m.group(1)) if m else None


def _seniority_match(jd: str, profile: ProfileFacts, weight: int) -> int:
    senior_terms = ["senior", "sr.", "lead", "principal", "staff"]
    junior_terms = ["junior", "jr.", "intern", "entry", "graduate"]
    if any(t in jd for t in senior_terms):
        # 4+ YOE matches "senior"; further seniority (Principal/Staff) is
        # blocked by the title filter in settings.yaml.
        return weight if profile.total_years_experience >= 3 else int(weight * 0.5)
    if any(t in jd for t in junior_terms):
        return int(weight * 0.6)  # over-qualified; still can apply
    return weight


def _rationale(matched: dict, missing: dict, yoe_have: int, yoe_needed: int | None) -> str:
    lines = []
    if matched["skills"]:
        lines.append(f"Matches: {', '.join(matched['skills'][:10])}")
    if matched["domains"]:
        lines.append(f"Domain overlap: {', '.join(matched['domains'])}")
    if missing["skills"]:
        lines.append(f"Missing from profile: {', '.join(missing['skills'][:6])}")
    if yoe_needed is not None:
        lines.append(f"Experience: profile {yoe_have}y vs required {yoe_needed}y")
    return " | ".join(lines) if lines else "No strong signals detected."
