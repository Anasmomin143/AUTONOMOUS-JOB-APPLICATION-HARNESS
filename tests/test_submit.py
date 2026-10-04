"""End-to-end `submit` runs: headless Chromium against a local form server.

Every test asserts on what the server actually received, so "nothing was
submitted" means no POST reached it.
"""
from __future__ import annotations
import datetime as dt
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from harness import modes, paths
from harness.automation import gate, runner
from harness.automation import playwright_driver as driver
from harness.state import read_json, write_json

if not driver.resolved_browser()[1]:
    pytest.skip("Chromium not installed (python -m playwright install chromium)", allow_module_level=True)

APP_ID = "APP-2026-0001"

FORM = """<!doctype html><html><body><h1>Frontend Engineer at Acme</h1>
<form action="{action}" method="post" enctype="multipart/form-data">
  <label for="first_name">First Name *</label><input id="first_name" name="first_name" required>
  <label for="last_name">Last Name *</label><input id="last_name" name="last_name" required>
  <label for="email">Email *</label><input id="email" name="email" type="email" required>
  <label for="phone">Phone</label><input id="phone" name="phone" type="tel">
  <label for="resume">Resume/CV *</label><input id="resume" name="resume" type="file" required>
  <label for="linkedin">LinkedIn Profile</label><input id="linkedin" name="linkedin">
  <label for="notice">What is your notice period?</label><input id="notice" name="notice" required>
  <label for="auth">Are you legally authorized to work in India?</label>
  <select id="auth" name="auth" required><option value="">Select...</option>
    <option value="1">Yes</option><option value="0">No</option></select>
  <fieldset><legend>Will you now or in the future require visa sponsorship?</legend>
    <label><input type="radio" name="sponsor" value="y" required> Yes</label>
    <label><input type="radio" name="sponsor" value="n"> No</label></fieldset>
  {extra}
  <button type="submit">Submit Application</button>
</form>
<footer>This site is protected by reCAPTCHA and the Google Privacy Policy.</footer>
</body></html>"""

EXTRAS = {
    "salary": '<label for="ctc">Expected CTC (INR)</label><input id="ctc" name="ctc" required>',
    "unknown": '<label for="k8s">How many years have you used Kubernetes?</label><input id="k8s" name="k8s" required>',
    "optional": '<label for="hear">How did you hear about us?</label><input id="hear" name="hear">',
    "captcha": '<iframe title="reCAPTCHA" src="about:blank" style="width:300px;height:80px"></iframe>',
    "jd_mfa": "<p>You will build MFA, OTP and two-factor login flows.</p>",
    "jd_security": "<p>Offers are subject to a security check.</p>",
    # A challenge the "user" solves: it disappears after 3 s.
    "captcha_temp": '<iframe id="cap" title="reCAPTCHA" src="about:blank" style="width:300px;height:80px"></iframe>'
                    '<script>setTimeout(() => document.getElementById("cap").remove(), 3000)</script>',
}

LANDING = '<!doctype html><html><body><h1>Frontend Engineer</h1><a href="/job">Apply now</a></body></html>'
THANKS = "<!doctype html><html><body><h1>Thank you for applying!</h1></body></html>"
SILENT = "<!doctype html><html><body><p>Something happened.</p></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def _send(self, body: str, code: int = 200) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        variants = (parse_qs(u.query).get("v") or [""])[0].split(",")
        if u.path == "/job":
            action = "/silent" if "silent" in variants else "/submit"
            self._send(FORM.format(action=action, extra="".join(EXTRAS.get(v, "") for v in variants)))
        elif u.path == "/landing":
            self._send(LANDING)
        else:
            self._send("not found", 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.posts.append((self.path, body))
        self._send(THANKS if self.path == "/submit" else SILENT)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.posts = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


@pytest.fixture
def site(server):
    server.posts.clear()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def url(path: str = "/job", *variants: str) -> str:
        return f"{base}{path}" + (f"?v={','.join(variants)}" if variants else "")
    url.posts = server.posts
    return url


def _app(job_url: str, **extra) -> dict:
    return {"application_id": APP_ID, "company": "acme", "role": "Frontend Engineer",
            "job_url": job_url, "job_source": "careers_page", "match_score": 88,
            "resume_type": "master", "resume_file": "master-resume.pdf",
            "status": "READY_FOR_APPROVAL", "date_applied": None, **extra}


def _seed(*apps: dict) -> None:
    write_json(paths.APPLICATIONS_JSON, {"applications": list(apps)})
    paths.MASTER_RESUME_PDF.write_bytes(b"%PDF-1.4 test resume\n")


def _record(app_id: str = APP_ID) -> dict:
    return next(a for a in read_json(paths.APPLICATIONS_JSON, {})["applications"]
                if a["application_id"] == app_id)


def _field(body: bytes, name: str) -> str | None:
    m = re.search(rb'name="' + name.encode() + rb'"\r\n\r\n(.*?)\r\n', body, re.S)
    return m.group(1).decode() if m else None


@pytest.fixture
def decider():
    """Answer prompts in order: decider(("approval", "YES"), ...). A
    decision may be a callable (side effects, then return the answer)."""
    stop = threading.Event()
    threads = []

    def start(*steps):
        def loop():
            seen: set[str] = set()
            for stage, decision in steps:
                while not stop.is_set():
                    p = read_json(gate.pending_path(APP_ID), {})
                    if p.get("stage") == stage and p.get("nonce") not in seen:
                        seen.add(p["nonce"])
                        answer = decision() if callable(decision) else decision
                        gate.decide(APP_ID, answer)
                        break
                    time.sleep(0.05)
        t = threading.Thread(target=loop, daemon=True)
        t.start()
        threads.append(t)

    yield start
    stop.set()
    for t in threads:
        t.join(timeout=2)


def _run(timeout: float = 15.0) -> int:
    return runner.run(APP_ID, headless=True, timeout=timeout, poll=0.05)


# ------------------------------------------------------------- supervised


def test_yes_fills_verifies_submits_and_records(site, decider, capsys):
    _seed(_app(site()))
    decider(("approval", "YES"))

    assert _run() == 0

    [(path, body)] = site.posts
    assert path == "/submit"
    assert _field(body, "first_name") == "Jordan" and _field(body, "last_name") == "Example"
    assert _field(body, "email") == "jordan@example.com"
    assert _field(body, "notice") == "Immediate"
    assert _field(body, "auth") == "1"           # "Yes" option of the select
    assert _field(body, "sponsor") == "y"        # "Yes — for roles outside India." -> "Yes"
    assert b'filename="master-resume.pdf"' in body
    rec = _record()
    assert rec["status"] == "APPLIED" and rec["date_applied"]
    assert rec["followup_date"] == (dt.date.today() + dt.timedelta(days=7)).isoformat()
    out = capsys.readouterr().out
    assert "APPLICATION READY" in out and "HARNESS_REQUEST: approval" in out


def test_silence_is_no(site):
    _seed(_app(site()))
    assert _run(timeout=1) == 12
    assert site.posts == []
    assert _record()["status"] == "READY_FOR_APPROVAL"


def test_no_declines_without_submitting(site, decider):
    _seed(_app(site()))
    decider(("approval", "NO"))
    assert _run() == 12
    assert site.posts == []
    assert _record()["status"] == "DECLINED"


def test_stale_decision_cannot_approve_a_new_prompt(site):
    _seed(_app(site()))
    write_json(gate.decision_path(APP_ID), {"decision": "YES", "nonce": "from-an-earlier-run"})
    assert _run(timeout=1) == 12
    assert site.posts == []


# ------------------------------------------------------------- questions


def test_stop_for_user_answer_blocks_and_required_field_cannot_be_skipped(site, decider, capsys):
    _seed(_app(site("/job", "salary")))
    # CONTINUE without answering: the required salary field is still
    # empty, so it asks again; then NO.
    decider(("input", "CONTINUE"), ("input", "NO"))
    assert _run() == 14
    assert site.posts == []
    out = capsys.readouterr().out
    assert "Expected CTC (INR) — screening-answers.yaml says always ask you" in out


def test_answer_added_to_yaml_is_used_after_continue(site, decider):
    _seed(_app(site("/job", "unknown")))

    def add_answer():
        with paths.SCREENING_ANSWERS.open("a", encoding="utf-8") as f:
            f.write('  - match: "(?i)years.*kubernetes"\n    answer: "0"\n')
        return "CONTINUE"

    decider(("input", add_answer), ("approval", "YES"))
    assert _run() == 0
    assert _field(site.posts[0][1], "k8s") == "0"


def test_optional_unknown_is_left_blank_after_continue(site, decider):
    _seed(_app(site("/job", "optional")))
    decider(("input", "CONTINUE"), ("approval", "YES"))
    assert _run() == 0
    assert _field(site.posts[0][1], "hear") == ""


# ------------------------------------------------------------- challenges


def test_captcha_halts_headless_without_submitting(site):
    _seed(_app(site("/job", "captcha")))
    assert _run() == 14
    assert site.posts == []


def test_captcha_is_handed_to_the_user(site, decider, monkeypatch):
    # A headed session (so it hands off) driving a headless browser.
    real_open = driver.open_browser
    monkeypatch.setattr(runner, "open_browser", lambda headless=False: real_open(headless=True))
    _seed(_app(site("/job", "captcha_temp")))

    def solved():
        time.sleep(3.5)  # the "user" solves it; the iframe goes away
        return "CONTINUE"

    decider(("takeover", solved), ("approval", "YES"))
    assert runner.run(APP_ID, headless=False, timeout=15, poll=0.05) == 0
    assert len(site.posts) == 1


def test_recaptcha_footer_text_is_not_a_challenge(site, decider):
    _seed(_app(site()))  # every form carries "protected by reCAPTCHA"
    decider(("approval", "YES"))
    assert _run() == 0


def test_job_description_mentioning_mfa_is_not_a_challenge(site, decider):
    _seed(_app(site("/job", "jd_mfa")))
    decider(("approval", "YES"))
    assert _run() == 0


def test_text_alarm_the_user_cleared_is_not_raised_again(site, decider, monkeypatch):
    real_open = driver.open_browser
    monkeypatch.setattr(runner, "open_browser", lambda headless=False: real_open(headless=True))
    _seed(_app(site("/job", "jd_security")))
    # Asked once; a second takeover prompt would never be answered and
    # the run would end with 14 instead of 0.
    decider(("takeover", "CONTINUE"), ("approval", "YES"))
    assert runner.run(APP_ID, headless=False, timeout=5, poll=0.05) == 0


# ------------------------------------------------------------- gates


def test_stop_sentinel_halts_while_waiting(site, decider):
    _seed(_app(site()))

    def stop():
        paths.STOP_SENTINEL.write_text("now")
        return "NO-OP"  # rejected by the gate; the STOP is what halts

    decider(("approval", stop))
    assert _run() == 11
    assert site.posts == []


def test_autonomous_needs_the_session_lock_too(site):
    policy = paths.AUTOMATION_POLICY_YAML
    policy.write_text(policy.read_text() + "\nmode: autonomous\nallow_application_submission: true\n")
    _seed(_app(site()))
    # Config locks alone: still supervised, so silence means NO.
    assert _run(timeout=1) == 12
    assert site.posts == []

    modes.confirm_session_autonomous()
    _seed(_app(site()))
    assert _run(timeout=1) == 0
    assert len(site.posts) == 1


def test_missing_confirmation_is_unverified_not_applied(site, decider):
    _seed(_app(site("/job", "silent")))
    decider(("approval", "YES"))
    assert _run() == 13
    assert len(site.posts) == 1  # it was submitted ...
    rec = _record()
    assert rec["status"] == "SUBMIT_UNVERIFIED"  # ... but never claimed as applied
    assert runner.run(APP_ID, headless=True, timeout=1) == 9  # and never resubmitted


def test_retry_cannot_reopen_a_submitted_application():
    from harness import cli
    _seed(_app("https://example.com/x", status="SUBMIT_UNVERIFIED"))
    assert cli.main(["retry", APP_ID]) == 9
    assert _record()["status"] == "SUBMIT_UNVERIFIED"
    _seed(_app("https://example.com/x", status="FAILED"))
    assert cli.main(["retry", APP_ID]) == 0
    assert _record()["status"] == "RETRY_PENDING"


def test_job_already_submitted_is_refused(site):
    _seed(_app(site()), _app(site(), application_id="APP-2026-0002", status="APPLIED"))
    assert _run() == 7
    assert site.posts == []


def test_apply_button_leads_to_the_form(site, decider):
    _seed(_app(site("/landing")))
    decider(("approval", "YES"))
    assert _run() == 0
    assert len(site.posts) == 1


def test_decide_only_accepts_answers_for_the_open_stage():
    assert gate.decide(APP_ID, "YES") == (False, f"No prompt is waiting for {APP_ID}.")
    gate.open_prompt(APP_ID, "approval")
    assert gate.decide(APP_ID, "CONTINUE")[0] is False
    assert gate.decide(APP_ID, "yes")[0] is True
