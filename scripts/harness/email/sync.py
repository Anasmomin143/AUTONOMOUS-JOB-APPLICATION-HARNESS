"""Bridge to mcp__Gmail__* tools.

The CLI can't call MCP tools directly — the slash-command wrapper does.
This module builds the request envelopes that the wrapper hands back.
For each application, it emits a `HARNESS_REQUEST: gmail_search` line;
the wrapper collects matching threads and re-invokes
`python -m harness.cli sync --ingest <path-to-mailbox.json>`.

`ingest_mailbox()` handles that second step — it reads a JSON list of
messages and matches them against `applications.json`.
"""
from __future__ import annotations
import json
from pathlib import Path

from .match import MatchResult, match_message, reconcile
from ..paths import APPLICATIONS_JSON
from ..state import read_json, write_json


def build_search_requests(apps: list[dict]) -> list[dict]:
    reqs: list[dict] = []
    for a in apps:
        company = a.get("company") or ""
        role = a.get("role") or ""
        app_id = a.get("application_id") or ""
        # Combine multi-signal query terms.
        q = " OR ".join(filter(None, [
            f"\"{app_id}\"" if app_id else "",
            f"\"{company}\"" if company else "",
        ])) or company or "job"
        reqs.append({
            "app_id": app_id,
            "query": q,
            "hint_terms": [company, role, app_id],
        })
    return reqs


def ingest_mailbox(path: Path) -> dict:
    if not path.exists():
        return {"error": f"mailbox file not found: {path}"}
    data = json.loads(path.read_text(encoding="utf-8"))
    apps = read_json(APPLICATIONS_JSON, {"applications": []}).get("applications", [])
    changed: list[dict] = []
    for msg in data.get("messages", []):
        m: MatchResult = match_message(msg, apps)
        if not m.application_id:
            continue
        if m.confidence == "review":
            for a in apps:
                if a.get("application_id") == m.application_id:
                    a["notes"] = (a.get("notes") or "") + f"\n[review] Weak email match; verify: {msg.get('subject','')}"
                    changed.append(a)
            continue
        for a in apps:
            if a.get("application_id") == m.application_id:
                new_email_status = m.status_signal
                a["email_status"] = new_email_status
                a["status"] = reconcile(a.get("status"), a.get("ats_status"), new_email_status)
                changed.append(a)
    write_json(APPLICATIONS_JSON, {"applications": apps})
    return {"updated": len(changed), "checked": len(apps)}
