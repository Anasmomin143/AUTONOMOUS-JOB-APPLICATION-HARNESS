"""Validate that a tailored resume never introduces claims that aren't
present in the master profile (spec §11)."""
from __future__ import annotations
import re
from dataclasses import dataclass

from ..profile import ProfileFacts


@dataclass
class ValidationResult:
    ok: bool
    problems: list[str]

    def report(self) -> str:
        if self.ok:
            return "OK — no fabricated tokens detected."
        return "REJECTED:\n  - " + "\n  - ".join(self.problems)


# Metrics not present in master are the highest-severity failure.
_METRIC_RX = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)\s*(%|percent|\+|x|users?|clients?|days?|weeks?)")


def validate(markdown: str, profile: ProfileFacts) -> ValidationResult:
    problems: list[str] = []
    profile_raw_lc = profile.raw_markdown.lower()

    # 1. Every metric in the tailored resume must exist verbatim in the master.
    for m in _METRIC_RX.finditer(markdown):
        chunk = m.group(0).lower()
        if chunk not in profile_raw_lc:
            problems.append(f"Metric not in master profile: {chunk!r}")

    # 2. Every employer / title / cert in the tailored resume must exist.
    for emp in profile.employers:
        pass  # allowed by construction
    # Reject any capitalized multi-word phrase that looks like an employer
    # but is not in profile.employers.
    known_lc = {e.lower() for e in profile.employers}
    for m in re.finditer(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})\b", markdown):
        phrase = m.group(1)
        if len(phrase.split()) <= 1:
            continue
        if phrase.lower() in known_lc:
            continue
        # A liberal allowlist: company-sounding phrases we saw in the master
        if phrase.lower() in profile_raw_lc:
            continue
        # Allow certification vendors already in master
        if any(phrase.lower() in c.lower() for c in profile.certifications):
            continue
        # Allow project product names in master
        if any(phrase.lower() in p.lower() for p in profile.projects):
            continue
        # Section headers we generated ourselves
        if phrase in {
            "Technical Skills", "Selected Projects", "Professional Experience",
            "Software Engineer", "Frontend Engineer", "Frontend Developer",
        }:
            continue
        problems.append(f"Possible fabricated proper noun: {phrase!r}")

    # 3. Detect obvious AI-cliché phrases.
    cliches = [
        "results-driven", "hit the ground running", "team player",
        "synergy", "leverage cutting-edge", "passionate about",
    ]
    for c in cliches:
        if c in markdown.lower():
            problems.append(f"Cliché phrase: {c!r}")

    return ValidationResult(ok=not problems, problems=problems)
