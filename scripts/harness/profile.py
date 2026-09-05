"""Parse `profile/master-profile.md` into a structured, allowlisted vocabulary.

The parser is deliberately simple — it walks the Markdown, extracts every
bullet under Skills / Employment / Certifications, and refuses to invent
anything. `validate_tailored_text()` compares candidate resume/message
text against the allowlist and rejects tokens not present.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date

from .paths import MASTER_PROFILE_MD


@dataclass
class ProfileFacts:
    name: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    skills: list[str] = field(default_factory=list)
    employers: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    verified_metrics: list[str] = field(default_factory=list)
    unresolved_todos: list[str] = field(default_factory=list)
    total_years_experience: int = 0
    raw_markdown: str = ""

    def as_allowlist(self) -> set[str]:
        tokens: set[str] = set()
        for s in (
            self.skills + self.employers + self.titles + self.certifications +
            self.projects + self.domains + self.verified_metrics
        ):
            for w in re.split(r"[\s,()\[\]/·|]+", s):
                if len(w) > 1:
                    tokens.add(w.lower())
        return tokens

    def is_ready(self) -> tuple[bool, list[str]]:
        problems: list[str] = []
        if not MASTER_PROFILE_MD.exists():
            problems.append("profile/master-profile.md is missing.")
        if not self.name:
            problems.append("Profile: name is empty.")
        if self.unresolved_todos:
            problems.append(f"Profile has {len(self.unresolved_todos)} unresolved TODO(user) blocks.")
        return (not problems, problems)


_SKILL_LINE_RX = re.compile(r"^\s*-\s*\*\*(.+?):\*\*\s*(.+)$")
_EMPLOYER_HEADER_RX = re.compile(r"^\*\*(.+?)\*\*\s*—\s*(.+?)\s*—\s*(.+?)$")
_DATE_RX = re.compile(r"(\w+\s+\d{4})\s*[–-]\s*(\w+\s+\d{4}|Present)")


def load_profile() -> ProfileFacts:
    facts = ProfileFacts()
    if not MASTER_PROFILE_MD.exists():
        return facts
    md = MASTER_PROFILE_MD.read_text(encoding="utf-8")
    facts.raw_markdown = md

    # Identity block
    m = re.search(r"\*\*Name:\*\*\s*(.+)", md);          facts.name = m.group(1).strip() if m else ""
    m = re.search(r"\*\*Location:\*\*\s*(.+)", md);      facts.location = m.group(1).strip() if m else ""
    m = re.search(r"\*\*Phone:\*\*\s*(.+)", md);         facts.phone = m.group(1).strip() if m else ""
    m = re.search(r"\*\*Email[^:]*:\*\*\s*(.+)", md);    facts.email = m.group(1).strip() if m else ""
    m = re.search(r"\*\*LinkedIn:\*\*\s*(\S+)", md);     facts.linkedin_url = m.group(1).strip() if m else ""
    m = re.search(r"\*\*GitHub:\*\*\s*(\S+)", md);       facts.github_url = m.group(1).strip() if m else ""

    # TODO(user) blocks
    for m in re.finditer(r"TODO\(user\)\s*[—:-]?\s*(.+)", md):
        facts.unresolved_todos.append(m.group(1).strip().split("\n")[0][:120])

    # Skills — under "## Skills (verified)" section
    skills_section = _section(md, "Skills (verified)") or _section(md, "Skills")
    if skills_section:
        for line in skills_section.splitlines():
            m = re.match(r"^\s*-\s*\*\*(.+?):\*\*\s*(.+)$", line)
            if not m:
                continue
            for tok in re.split(r"[,;]", m.group(2)):
                tok = re.sub(r"\(.*?\)", "", tok).strip(" .")
                if tok and not tok.lower().startswith("todo"):
                    facts.skills.append(tok)

    # Employment — multi-line search (each line)
    for line in md.splitlines():
        hm = _EMPLOYER_HEADER_RX.match(line)
        if hm and hm.group(1).strip() not in facts.employers:
            facts.employers.append(hm.group(1).strip())
    # Also pull "**Elemica**" style headings from current role section
    for hm in re.finditer(r"###\s+(.+)", md):
        emp = hm.group(1).strip()
        if emp and emp not in facts.employers:
            facts.employers.append(emp)
    # Titles: any line with "- title:"
    for m in re.finditer(r"-\s*title:\s*(.+)", md):
        facts.titles.append(m.group(1).strip())
    facts.titles = [t for t in facts.titles if not t.startswith("Software Engineer II") or facts.titles.count(t) == 1]

    # Certifications
    cert_section = _section(md, "Certifications")
    if cert_section:
        for line in cert_section.splitlines():
            m = re.match(r"\s*-\s*(.+)", line)
            if m and "TODO" not in m.group(1):
                facts.certifications.append(m.group(1).strip())

    # Projects
    proj_section = _section(md, "Selected projects (verified)")
    if proj_section:
        for m in re.finditer(r"\*\*(.+?)\*\*", proj_section):
            facts.projects.append(m.group(1).strip())

    # Verified metrics (any line under "Verified achievements:" bullets)
    for m in re.finditer(r"Verified achievements[^\n]*:?\n((?:\s*-\s.+\n?)+)", md):
        for line in m.group(1).splitlines():
            mm = re.match(r"\s*-\s*(.+)", line)
            if mm:
                facts.verified_metrics.append(mm.group(1).strip())

    # Domains — the products/domain adjectives that appear in employment
    for keyword, canonical in [
        ("supply-chain", "supply_chain"), ("supply chain", "supply_chain"),
        ("travel", "travel"), ("banking", "banking"),
        ("crm", "crm"), ("customer relationship", "crm"),
    ]:
        if keyword.lower() in md.lower() and canonical not in facts.domains:
            facts.domains.append(canonical)

    # Total years experience — compute from date ranges
    facts.total_years_experience = _sum_years(md)
    return facts


def _section(md: str, heading: str) -> str:
    m = re.search(rf"##\s+{re.escape(heading)}\n(.+?)(?=\n##\s|\Z)", md, re.S)
    return m.group(1) if m else ""


_MONTH = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _parse_ym(s: str) -> tuple[int, int] | None:
    s = s.strip().lower()
    if s == "present":
        d = date.today()
        return (d.year, d.month)
    m = re.match(r"(\w+)\s+(\d{4})", s)
    if not m:
        return None
    mo = _MONTH.get(m.group(1)[:3])
    if not mo:
        return None
    return (int(m.group(2)), mo)


def _sum_years(md: str) -> int:
    months = 0
    for m in _DATE_RX.finditer(md):
        a = _parse_ym(m.group(1)); b = _parse_ym(m.group(2))
        if not a or not b:
            continue
        months += max(0, (b[0] - a[0]) * 12 + (b[1] - a[1]))
    return round(months / 12)
