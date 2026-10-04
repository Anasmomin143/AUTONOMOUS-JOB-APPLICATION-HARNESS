"""Bridge to mcp__Gmail__* tools.

The CLI can't call MCP tools directly — the slash-command wrapper does.
`build_search_requests()` emits one `HARNESS_REQUEST: gmail_search` per
submitted application; the wrapper collects the matching messages into
`{"messages": [{"id", "date", "from", "subject", "body"}]}` and re-invokes
`python -m harness.cli sync --ingest <path>`, handled by `ingest_mailbox()`.
"""
from __future__ import annotations
import datetime as dt
import email.utils
import hashlib
import json
import re
from pathlib import Path

from dateutil import parser as date_parser

from .match import match_message
from ..paths import APPLICATIONS_JSON
from ..state import read_json, write_json

# Applications that can receive employer email: already submitted.
SUBMITTED = ("APPLIED", "SUBMITTED", "SUBMIT_UNVERIFIED", "CONFIRMED",
             "ASSESSMENT", "INTERVIEW", "OFFER", "REJECTED")
_FUNNEL = {"SUBMITTED": 1, "SUBMIT_UNVERIFIED": 1, "APPLIED": 1,
           "CONFIRMED": 2, "ASSESSMENT": 3, "INTERVIEW": 4}
_TERMINAL = ("REJECTED", "OFFER")
_NEXT_ACTION = {"CONFIRMED": "AWAIT_RESPONSE", "ASSESSMENT": "COMPLETE_ASSESSMENT",
                "INTERVIEW": "SCHEDULE_INTERVIEW", "OFFER": "REVIEW_OFFER", "REJECTED": None}


def next_status(current: str, signal: str) -> str:
    """Status after an email announcing `signal`. Rejections and offers
    end the funnel from anywhere; otherwise status only moves forward, so
    a late "application received" never undoes an interview."""
    cur = (current or "").upper()
    if signal not in _NEXT_ACTION or cur in _TERMINAL:
        return cur
    if signal in _TERMINAL:
        return signal
    return signal if _FUNNEL.get(signal, 0) > _FUNNEL.get(cur, 0) else cur


def _parse_date(value) -> dt.datetime | None:
    """Gmail gives RFC 2822 headers or epoch milliseconds; always returns
    an aware datetime (naive values are taken as local time)."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            n = int(value)
            return dt.datetime.fromtimestamp(n / 1000 if n > 10**11 else n, tz=dt.timezone.utc)
        try:
            d = email.utils.parsedate_to_datetime(str(value))
        except (TypeError, ValueError):
            d = date_parser.parse(str(value))
    except (ValueError, OverflowError):
        return None
    return d if d.tzinfo else d.astimezone()


def _search_name(company: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (company or "").lower()))


def build_search_requests(apps: list[dict]) -> list[dict]:
    reqs: list[dict] = []
    for a in apps:
        if (a.get("status") or "").upper() not in SUBMITTED:
            continue
        name = _search_name(a.get("company"))
        if not name:
            continue
        query = f'"{name}"'
        applied = _parse_date(a.get("date_applied"))
        if applied:
            # Gmail's after: is day-granular; ingest filters exactly.
            query += f" after:{(applied.date() - dt.timedelta(days=1)):%Y/%m/%d}"
        reqs.append({
            "app_id": a.get("application_id"),
            "query": query,
            "hint_terms": [a.get("company"), a.get("role"), a.get("requisition_id")],
        })
    return reqs


def _message_id(msg: dict) -> str:
    if msg.get("id"):
        return str(msg["id"])
    raw = "|".join(str(msg.get(k) or "") for k in ("date", "from", "subject"))
    return "sha1:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def ingest_mailbox(path: Path) -> dict:
    if not path.exists():
        return {"error": f"mailbox file not found: {path}"}
    messages = json.loads(path.read_text(encoding="utf-8")).get("messages", [])
    data = read_json(APPLICATIONS_JSON, {"applications": []})
    apps = data.get("applications", [])
    by_id = {a.get("application_id"): a for a in apps}
    candidates = [a for a in apps if (a.get("status") or "").upper() in SUBMITTED]

    # Oldest first, so the latest email decides the status.
    dated = [(_parse_date(m.get("date")), m) for m in messages]
    dated.sort(key=lambda p: (p[0] is None, p[0] or dt.datetime.min.replace(tzinfo=dt.timezone.utc)))

    report: dict = {"messages": len(messages), "updated": [], "review": [], "ignored": 0, "already_seen": 0}
    now = dt.datetime.now().isoformat(timespec="seconds")
    for when, msg in dated:
        m = match_message(msg, candidates)
        subject = str(msg.get("subject") or "")[:200]
        if m.confidence == "none":
            report["ignored"] += 1
            continue
        if m.confidence == "ambiguous":
            if m.status_signal != "UNKNOWN":
                report["review"].append({"candidates": m.candidates, "signal": m.status_signal,
                                         "subject": subject, "why": "matches several applications equally"})
            continue
        app = by_id[m.application_id]
        applied = _parse_date(app.get("date_applied"))
        if when and applied and when.date() < applied.date():
            report["ignored"] += 1  # predates the application
            continue
        events = app.setdefault("email_events", [])
        mid = _message_id(msg)
        if any(e.get("id") == mid for e in events):
            report["already_seen"] += 1
            continue
        if m.confidence != "high" and m.status_signal == "UNKNOWN":
            report["ignored"] += 1  # weak match, nothing announced: marketing / noise
            continue
        events.append({"id": mid, "date": when.isoformat() if when else None, "subject": subject,
                       "signal": m.status_signal, "confidence": m.confidence, "signals": m.signals})
        if m.confidence != "high":
            app["notes"] = "\n".join(filter(None, [
                app.get("notes"),
                f"[review] Possible {m.status_signal} email, weak match ({', '.join(m.signals)}): {subject}"]))
            app["last_update"] = now
            report["review"].append({"app_id": m.application_id, "signal": m.status_signal,
                                     "subject": subject, "why": f"only {', '.join(m.signals)} matched"})
            continue
        old = (app.get("status") or "").upper()
        new = next_status(old, m.status_signal)
        if m.status_signal != "UNKNOWN":
            app["email_status"] = m.status_signal
        if new != old:
            app["status"] = new
            app["next_action"] = _NEXT_ACTION.get(new, app.get("next_action"))
            report["updated"].append({"app_id": m.application_id, "from": old, "to": new, "subject": subject})
        app["last_update"] = now
    write_json(APPLICATIONS_JSON, data)
    return report
