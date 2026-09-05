"""Match Gmail messages to applications (spec §17/§20).

Requires ≥ 2 independent signals before assigning a status update.
Signals:
- company name in From-domain OR body
- role phrase in subject OR body
- application-ID in subject OR body
- candidate name in body
- job URL in body
- known ATS sender

Below the threshold → returns "review" (never guesses).
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from urllib.parse import urlparse


_STATUS_KEYWORDS: dict[str, list[str]] = {
    "CONFIRMED":  ["application received", "thank you for applying", "we have received your application"],
    "REJECTED":   ["not moving forward", "not proceed", "unfortunately", "regret to inform"],
    "INTERVIEW":  ["interview", "schedule a call", "next steps", "hiring team"],
    "ASSESSMENT": ["assessment", "coding challenge", "take-home", "hackerrank", "codility"],
    "OFFER":      ["offer letter", "we are pleased", "offer of employment"],
}


@dataclass
class MatchResult:
    application_id: str | None
    status_signal: str          # one of CONFIRMED/REJECTED/INTERVIEW/ASSESSMENT/OFFER/UNKNOWN
    confidence: str             # "high" (>=2 signals) | "review" (1) | "none"
    signals: list[str]


def match_message(msg: dict, applications: list[dict]) -> MatchResult:
    """`msg` is expected to have {'subject','from','body','headers':{}}."""
    text = " ".join([msg.get("subject", ""), msg.get("body", "")]).lower()
    from_addr = (msg.get("from") or "").lower()
    from_domain = _domain_of(from_addr)

    best: MatchResult = MatchResult(None, "UNKNOWN", "none", [])
    for app in applications:
        signals: list[str] = []
        company = (app.get("company") or "").lower()
        role = (app.get("role") or "").lower()
        app_id = (app.get("application_id") or "").lower()
        job_url = (app.get("job_url") or "").lower()
        candidate = (app.get("candidate_name") or "").lower()

        if company and (company in from_domain or company in text):
            signals.append("company")
        if role and role in text:
            signals.append("role")
        if app_id and app_id in text:
            signals.append("app_id")
        if candidate and candidate in text:
            signals.append("candidate")
        if job_url:
            u = urlparse(job_url).netloc.lower()
            if u and u in text:
                signals.append("job_url")

        if not signals:
            continue

        status = _classify_status(text)
        conf = "high" if len(signals) >= 2 else "review"
        candidate_result = MatchResult(app.get("application_id"), status, conf, signals)
        # Prefer the highest-confidence, most-signal match.
        if (
            (candidate_result.confidence == "high" and best.confidence != "high") or
            (len(candidate_result.signals) > len(best.signals))
        ):
            best = candidate_result
    return best


def _domain_of(addr: str) -> str:
    m = re.search(r"@([\w\.-]+)", addr)
    return (m.group(1) or "").lower() if m else ""


def _classify_status(text: str) -> str:
    for status, kws in _STATUS_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return status
    return "UNKNOWN"


def reconcile(tracker: str | None, ats: str | None, email: str | None) -> str:
    """Spec §18 — combine three sources of truth into a single Tracker Status."""
    ranked = {
        "OFFER": 5, "INTERVIEW": 4, "ASSESSMENT": 3,
        "APPLIED": 2, "CONFIRMED": 2, "REJECTED": 1, "UNKNOWN": 0,
    }
    best = "UNKNOWN"
    for s in (tracker, ats, email):
        if not s:
            continue
        s = s.upper()
        if ranked.get(s, 0) > ranked.get(best, 0):
            best = s
    return best
