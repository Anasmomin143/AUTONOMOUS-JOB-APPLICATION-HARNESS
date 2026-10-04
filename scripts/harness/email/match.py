"""Match Gmail messages to applications and classify them (spec §17–20).

A status change needs two kinds of evidence about the same application:

- company — the sender's domain or the subject/body names the company;
- job     — the role title, requisition ID, application ID or job URL.

Company evidence alone (marketing mail, another role at the same
company) is at most a review note. The candidate's own name is not a
signal: it is in nearly every email they receive.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Checked in this order; the first status with a matching phrase wins.
# Rejections come first because they routinely open with "thank you for
# applying", and interview invites with "we are pleased".
_STATUS_PATTERNS: list[tuple[str, list[str]]] = [
    ("REJECTED", [
        r"(not|won'?t) (be )?moving forward", r"not (be )?progressing", r"will not progress",
        r"decided not to (proceed|progress|move forward)",
        r"(pursue|proceed|move forward) with other candidates", r"regret to inform",
        r"position has been filled", r"no longer (being )?considered", r"unable to offer you",
        r"will not be (proceeding|continuing|offering)", r"(have|has|were|was) not (been )?selected",
    ]),
    ("OFFER", [
        r"offer letter", r"offer of employment", r"pleased to (offer|extend)",
        r"extend (you )?an offer", r"(formal|verbal|job) offer",
    ]),
    ("INTERVIEW", [
        r"invite you to (an? )?(interview|call|phone screen|chat|conversation)",
        r"schedule (an? |your )?(interview|call|phone screen|chat|time to (talk|chat|speak))",
        r"(like|love) to (schedule|set up|arrange) (an? )?(interview|call|chat|time)",
        r"(like|love) to (speak|chat|talk) with you", r"your (upcoming |scheduled )?interview",
        r"interview (invitation|invite|request|confirmation)",
        r"availability for (an? )?(interview|call|chat)", r"next round",
    ]),
    ("ASSESSMENT", [
        r"\bassessment\b", r"coding (challenge|exercise|test)", r"take[- ]home",
        r"hackerrank", r"codility", r"codesignal", r"online test",
    ]),
    ("CONFIRMED", [
        r"application (has been |was )?(received|submitted)",
        r"thank(s| you) for (applying|your application|submitting)",
        r"we('ve| have) received your application", r"successfully (applied|submitted)",
    ]),
]
_COMPILED = [(status, [re.compile(p) for p in pats]) for status, pats in _STATUS_PATTERNS]
# "If selected, we'll schedule an interview" describes a possibility, not an event.
_CONDITIONAL_RX = re.compile(r"\b(if|should|may|might|once|whether|in the event)\b")


@dataclass
class MatchResult:
    application_id: str | None
    status_signal: str          # CONFIRMED / REJECTED / INTERVIEW / ASSESSMENT / OFFER / UNKNOWN
    confidence: str             # "high" | "review" | "ambiguous" | "none"
    signals: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)  # when ambiguous


def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def classify(text: str) -> str:
    """Status the message announces, judged sentence by sentence; a
    conditional sentence ("if selected…") announces nothing."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", _norm(text))
    for status, patterns in _COMPILED:
        for sentence in sentences:
            for rx in patterns:
                m = rx.search(sentence)
                if m and (status == "CONFIRMED" or not _CONDITIONAL_RX.search(sentence[:m.start()])):
                    return status
    return "UNKNOWN"


def _domain_of(addr: str) -> str:
    m = re.search(r"@([\w.\-]+)", addr or "")
    return m.group(1).lower() if m else ""


def _company_named(company: str, text: str) -> bool:
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    if not tokens:
        return False
    return re.search(r"\b" + r"[\s\-_.]*".join(map(re.escape, tokens)) + r"\b", text) is not None


def _company_domain(company: str, domain: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", company.lower())
    return len(compact) >= 3 and compact in re.split(r"[.\-]", domain)


def _role_named(role: str, text: str) -> bool:
    r = _norm(role)
    if not r:
        return False
    if r in text:
        return True
    # "Frontend Engineer, Platform" is often written "Frontend Engineer".
    head = re.split(r"\s*(?:,|\(|\||\s[-–—]\s)\s*", r)[0]
    return len(head.split()) >= 2 and head in text


def _job_signals(app: dict, text: str) -> list[str]:
    sig: list[str] = []
    if _role_named(app.get("role") or "", text):
        sig.append("role")
    req = _norm(app.get("requisition_id"))
    if len(req) >= 4 and re.search(rf"\b{re.escape(req)}\b", text):
        sig.append("requisition_id")
    app_id = _norm(app.get("application_id"))
    if app_id and app_id in text:
        sig.append("app_id")
    url = urlparse(app.get("job_url") or "")
    if url.netloc and len(url.path) > 1 and _norm(url.netloc + url.path) in text:
        sig.append("job_url")
    return sig


def match_message(msg: dict, applications: list[dict]) -> MatchResult:
    """`msg` has {'subject','from','body'}; `applications` are the ones
    that may receive email (already submitted)."""
    text = _norm(f"{msg.get('subject', '')}\n{msg.get('body', '')}")
    domain = _domain_of(msg.get("from") or "")
    status = classify(f"{msg.get('subject', '')}\n{msg.get('body', '')}")

    scored: list[tuple[int, int, dict, list[str]]] = []  # (high?, n_job, app, signals)
    for app in applications:
        company = app.get("company") or ""
        company_sig = (["sender_domain"] if domain and _company_domain(company, domain) else []) \
            + (["company_named"] if _company_named(company, text) else [])
        job_sig = _job_signals(app, text)
        if company_sig or job_sig:
            scored.append((int(bool(company_sig and job_sig)), len(job_sig), app, company_sig + job_sig))
    if not scored:
        return MatchResult(None, status, "none")

    best = max((h, n) for h, n, _, _ in scored)
    top = [(app, sig) for h, n, app, sig in scored if (h, n) == best]
    confidence = "high" if best[0] else "review"
    if len(top) > 1:
        return MatchResult(None, status, "ambiguous", [],
                           [a.get("application_id") for a, _ in top])
    app, signals = top[0]
    return MatchResult(app.get("application_id"), status, confidence, signals)
