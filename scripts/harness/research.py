"""Company research (spec §4/§32).

For a first-pass implementation this returns a request envelope that
Claude Code executes via WebSearch/WebFetch. The CLI prints
`HARNESS_REQUEST: research <json>` and expects the slash-command wrapper
to hand it back through `--resume <id>` — but that plumbing is optional:
if the caller passes `--offline`, the function returns a stub brief that
downstream tailoring can still consume.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Brief:
    company: str
    summary: str
    products: list[str]
    tech_hints: list[str]
    culture_hints: list[str]
    risks: list[str]


def offline_brief(company: str, seed_desc: str = "") -> Brief:
    return Brief(
        company=company,
        summary=(seed_desc or f"Offline brief for {company}. Enable /research online to enrich.")[:400],
        products=[],
        tech_hints=[],
        culture_hints=[],
        risks=["Brief was generated offline; verify claims before recruiter contact."],
    )
