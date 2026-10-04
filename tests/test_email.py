import json

import pytest

from harness import cli, paths
from harness.email.match import classify, match_message
from harness.email.sync import build_search_requests, ingest_mailbox, next_status
from harness.state import read_json, write_json

NAME = "Jordan Example"


def _app(app_id="APP-2026-0001", role="Frontend Engineer, Platform", status="APPLIED",
         date_applied="2026-09-10T10:00:00", **extra):
    return {"application_id": app_id, "company": "airbnb", "role": role,
            "job_url": "https://careers.airbnb.com/positions/123", "requisition_id": "8154749",
            "status": status, "date_applied": date_applied, "candidate_name": NAME, **extra}


def _msg(body, subject="Your application", sender="no-reply@airbnb.com", id=None, date=None):
    m = {"subject": subject, "from": sender, "body": body}
    if id:
        m["id"] = id
    if date:
        m["date"] = date
    return m


# ------------------------------------------------------------- classify


@pytest.mark.parametrize("text, expected", [
    # Rejections usually open with thanks; used to be read as CONFIRMED.
    ("Thank you for applying. Unfortunately, we will not be moving forward.", "REJECTED"),
    ("We have decided to move forward with other candidates.", "REJECTED"),
    ("We are pleased to invite you to an interview next week.", "INTERVIEW"),  # not an OFFER
    ("We'd like to schedule a call to discuss the role.", "INTERVIEW"),
    ("We are pleased to offer you the position. Your offer letter is attached.", "OFFER"),
    ("Please complete the HackerRank assessment within 5 days.", "ASSESSMENT"),
    ("We have received your application. Our hiring team will review it.", "CONFIRMED"),
    # A possibility is not an event.
    ("Thanks for applying! If selected, we'll schedule an interview.", "CONFIRMED"),
    ("If we decide not to move forward, we'll let you know.", "UNKNOWN"),
    ("Plan your next steps for summer with the Airbnb team.", "UNKNOWN"),
])
def test_classify(text, expected):
    assert classify(text) == expected


# ------------------------------------------------------------- matching


def test_company_and_your_name_alone_are_not_a_match():
    # Used to be "INTERVIEW, high confidence": company + candidate name.
    promo = _msg(f"Hi {NAME}, plan your next steps for summer with the Airbnb team.",
                 subject="Your next trip", sender="news@airbnb.com")
    m = match_message(promo, [_app()])
    assert m.confidence == "review" and m.status_signal == "UNKNOWN"


def test_company_plus_role_is_high_confidence():
    m = match_message(_msg("Thanks for applying to Frontend Engineer at Airbnb."), [_app()])
    assert (m.application_id, m.confidence, m.status_signal) == ("APP-2026-0001", "high", "CONFIRMED")
    assert set(m.signals) == {"sender_domain", "company_named", "role"}


def test_role_picks_the_right_application_at_the_same_company():
    apps = [_app(), _app("APP-2026-0002", role="UI Engineer", job_url="https://x/2", requisition_id="999")]
    m = match_message(_msg("Your UI Engineer application at Airbnb was received."), apps)
    assert m.application_id == "APP-2026-0002"


def test_equal_matches_are_ambiguous():
    apps = [_app(), _app("APP-2026-0002", role="UI Engineer", requisition_id="999")]
    m = match_message(_msg("Unfortunately we are not moving forward with your Airbnb application."), apps)
    assert m.confidence == "ambiguous" and set(m.candidates) == {"APP-2026-0001", "APP-2026-0002"}


# ------------------------------------------------------------- status rules


@pytest.mark.parametrize("current, signal, expected", [
    ("APPLIED", "REJECTED", "REJECTED"),         # used to stay APPLIED
    ("INTERVIEW", "REJECTED", "REJECTED"),
    ("INTERVIEW", "CONFIRMED", "INTERVIEW"),     # a late confirmation never goes backwards
    ("REJECTED", "INTERVIEW", "REJECTED"),
    ("SUBMIT_UNVERIFIED", "CONFIRMED", "CONFIRMED"),
    ("APPLIED", "UNKNOWN", "APPLIED"),
])
def test_next_status(current, signal, expected):
    assert next_status(current, signal) == expected


# ------------------------------------------------------------- ingest


def _ingest(tmp_path, *messages):
    p = tmp_path / "mailbox.json"
    p.write_text(json.dumps({"messages": list(messages)}))
    return ingest_mailbox(p)


def _rec(app_id="APP-2026-0001"):
    return next(a for a in read_json(paths.APPLICATIONS_JSON, {})["applications"] if a["application_id"] == app_id)


def test_latest_email_decides_even_when_listed_out_of_order(tmp_path):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app()]})
    rejection = _msg("Frontend Engineer at Airbnb: we regret to inform you we will not be moving forward.",
                     id="m2", date="Tue, 22 Sep 2026 09:00:00 +0530")
    confirmation = _msg("Thanks for applying to Frontend Engineer at Airbnb.",
                        id="m1", date="Thu, 10 Sep 2026 11:00:00 +0530")
    report = _ingest(tmp_path, rejection, confirmation)
    assert _rec()["status"] == "REJECTED" and _rec()["next_action"] is None
    assert [u["to"] for u in report["updated"]] == ["CONFIRMED", "REJECTED"]


def test_reingesting_is_idempotent(tmp_path):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app()]})
    weak = _msg("Unfortunately we are not moving forward with your Airbnb application.", id="w1")
    _ingest(tmp_path, weak)
    report = _ingest(tmp_path, weak)
    rec = _rec()
    assert report["already_seen"] == 1
    assert len(rec["email_events"]) == 1
    assert rec["notes"].count("[review]") == 1
    assert rec["status"] == "APPLIED"  # weak match: a review note, never a status change


def test_mail_from_before_applying_is_ignored(tmp_path):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app()]})
    old = _msg("Frontend Engineer at Airbnb: we are not moving forward.", id="o1",
               date="Mon, 01 Jun 2026 09:00:00 +0000")
    report = _ingest(tmp_path, old)
    assert report["ignored"] == 1 and _rec()["status"] == "APPLIED"


def test_unsubmitted_applications_never_change(tmp_path):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app(status="READY_FOR_APPROVAL", date_applied=None)]})
    _ingest(tmp_path, _msg("We'd like to schedule an interview for Frontend Engineer at Airbnb."))
    assert _rec()["status"] == "READY_FOR_APPROVAL"


def test_gmail_epoch_millis_dates_are_understood(tmp_path):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app()]})
    # 2026-09-15 as Gmail internalDate (ms).
    _ingest(tmp_path, _msg("We'd like to schedule an interview for Frontend Engineer at Airbnb.",
                           id="i1", date="1789459200000"))
    assert _rec()["status"] == "INTERVIEW"


# ------------------------------------------------------------- search + CLI


def test_searches_only_submitted_applications_since_they_were_sent():
    reqs = build_search_requests([_app(), _app("APP-2026-0002", status="READY_FOR_APPROVAL")])
    assert [r["app_id"] for r in reqs] == ["APP-2026-0001"]
    assert reqs[0]["query"] == '"airbnb" after:2026/09/09'


def test_sync_cli_reports_changes(tmp_path, capsys):
    write_json(paths.APPLICATIONS_JSON, {"applications": [_app()]})
    p = tmp_path / "mailbox.json"
    p.write_text(json.dumps({"messages": [
        _msg("We'd like to schedule an interview for Frontend Engineer at Airbnb.", id="i1")]}))
    assert cli.main(["sync", "--ingest", str(p)]) == 0
    out = capsys.readouterr().out
    assert "UPDATED APP-2026-0001: APPLIED → INTERVIEW" in out
