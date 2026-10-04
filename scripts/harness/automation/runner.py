"""Drive one prepared application through the browser (spec §12–14).

    harness submit --app-id APP-YYYY-NNNN

Opens the form, fills identity fields from the profile, uploads the
recorded resume, answers screening questions from
messages/screening-answers.yaml, then stops at the approval gate. It
submits only on the user's YES — or, in autonomous mode, only when all
three locks are set — and records APPLIED only after a confirmation page
is verified. Anything it cannot answer, and every CAPTCHA / MFA / OTP,
is handed to the user. Silence is NO.

Exit codes:
   0  APPLIED — submitted and confirmation verified
   1  FAILED — unexpected error before submitting (see error_reason)
   3  application not found
   7  this job already has a submitted application
   8  resume file missing
   9  status doesn't allow submission
  10  daily cap reached
  11  halted by /stop — nothing submitted
  12  not approved (NO, or silence until the timeout) — nothing submitted
  13  SUBMIT_UNVERIFIED — submit was clicked, confirmation not found
  14  halted at unanswered questions / a challenge / no form — nothing submitted
"""
from __future__ import annotations
import datetime as dt
import os
import sys
from pathlib import Path

from .. import modes
from ..config import Config
from ..paths import APPLICATIONS_JSON, MASTER_RESUME_PDF, RESUMES_DIR
from ..profile import load_profile
from ..state import read_json, write_json
from ..tracker import activity
from . import answers as answers_mod
from . import form, gate, safety
from .ats import pick_adapter
from .playwright_driver import StopRequested, check_stop, checkpoint, open_browser, screenshot

SUBMITTABLE = ("READY_FOR_APPROVAL", "RETRY_PENDING")
SUBMITTED_LIKE = ("APPLIED", "SUBMITTED", "SUBMIT_UNVERIFIED", "CONFIRMED",
                  "ASSESSMENT", "INTERVIEW", "OFFER", "REJECTED")
_EMBEDDED_ATS_JS = """() => {
  const f = Array.from(document.querySelectorAll('iframe[src]'))
    .find(i => /greenhouse\\.io|lever\\.co|ashbyhq\\.com/.test(i.src));
  return f ? f.src : null;
}"""


class Halt(Exception):
    """Stop without submitting; `code` is the exit code."""

    def __init__(self, code: int, note: str):
        super().__init__(note)
        self.code = code
        self.note = note


def say(*parts) -> None:
    print(*parts, flush=True)


def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def _load_apps() -> list[dict]:
    return read_json(APPLICATIONS_JSON, {"applications": []}).get("applications", [])


def _applied_today(apps: list[dict]) -> int:
    today = dt.date.today().isoformat()
    return sum(1 for a in apps if str(a.get("date_applied") or "").startswith(today))


def _resume_path(app: dict) -> Path:
    if (app.get("resume_type") or "").lower() == "tailored":
        return RESUMES_DIR / "tailored" / str(app.get("resume_file") or "")
    return MASTER_RESUME_PDF


def run(app_id: str, *, headless: bool | None = None, timeout: float = 900.0,
        poll: float = 1.0, on_update=None) -> int:
    cfg = Config.load()
    apps = _load_apps()
    app = next((a for a in apps if a.get("application_id") == app_id), None)
    if app is None:
        say(f"{app_id!r} not found in applications.json.")
        return 3
    status = (app.get("status") or "").upper()
    if status not in SUBMITTABLE:
        say(f"Refused: {app_id} is {status or 'without a status'}; only "
            f"{' / '.join(SUBMITTABLE)} applications can be submitted.")
        return 9
    url = _norm(app.get("job_url"))
    dup = next((a for a in apps if a is not app and url and _norm(a.get("job_url")) == url
                and (a.get("status") or "").upper() in SUBMITTED_LIKE), None)
    if dup:
        say(f"Refused: this job was already submitted as {dup.get('application_id')}. Never apply twice.")
        return 7
    if _applied_today(apps) >= cfg.max_per_day:
        say(f"Refused: daily cap reached ({cfg.max_per_day} applications today, max_applications_per_day).")
        return 10
    resume = _resume_path(app)
    if not resume.is_file():
        say(f"Refused: resume not found at {resume}.")
        return 8
    try:
        check_stop()
    except StopRequested as e:
        say(f"Refused: {e} Delete state/STOP to resume.")
        return 11

    if headless is None:
        headless = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
        if headless:
            say("No display found: running headless. You won't see the browser, so CAPTCHAs and "
                "browser-only answers can't be handed to you — the run will stop there instead.")

    session = _Session(app, cfg, resume, headless=headless, timeout=timeout, poll=poll, on_update=on_update)
    pw, context = open_browser(headless=headless)
    try:
        session.page = context.pages[0] if context.pages else context.new_page()
        return session.drive()
    except Exception as e:
        return session.fail(e)
    finally:
        gate.close_prompt(app_id)
        try:
            context.close()
        finally:
            pw.stop()


class _Session:
    def __init__(self, app: dict, cfg: Config, resume: Path, *, headless: bool,
                 timeout: float, poll: float, on_update):
        self.app = app
        self.app_id = app["application_id"]
        self.cfg = cfg
        self.resume = resume
        self.headless = headless
        self.timeout = timeout
        self.poll = poll
        self.on_update = on_update
        self.profile = load_profile()
        self.rules = answers_mod.load()
        self.adapter = pick_adapter(app)
        self.page = None
        self.clicked = False  # once True, the outcome can never be "nothing submitted"
        self.dismissed: dict[str, set[str]] = {}  # url -> text-only challenge reasons the user cleared

    # ------------------------------------------------------------ records

    def _update(self, **fields) -> None:
        data = read_json(APPLICATIONS_JSON, {"applications": []})
        for a in data.get("applications", []):
            if a.get("application_id") == self.app_id:
                if "notes" in fields:
                    fields["notes"] = "\n".join(filter(None, [a.get("notes"), fields["notes"]]))
                a.update(fields)
                a["last_update"] = dt.datetime.now().isoformat(timespec="seconds")
        write_json(APPLICATIONS_JSON, data)
        if self.on_update:
            self.on_update()

    def _record_applied(self, evidence: str, by: str) -> int:
        follow = dt.date.today() + dt.timedelta(days=int((self.cfg.policy.get("followup") or {}).get("first_after_days", 7)))
        self._update(status="APPLIED", date_applied=dt.datetime.now().isoformat(timespec="seconds"),
                     ats_status="SUBMITTED", followup_date=follow.isoformat(), next_action="AWAIT_RESPONSE",
                     error_reason=None, notes=f"Submitted by {by}; verified: {evidence}")
        activity.log(self.app_id, "APPLIED", evidence)
        say(f"\nSUBMITTED AND VERIFIED: {self.app_id} — {evidence}")
        say(f"Follow-up date: {follow.isoformat()}")
        return 0

    def _record_unverified(self, evidence: str) -> int:
        self._update(status="SUBMIT_UNVERIFIED", error_reason=evidence, next_action="VERIFY_MANUALLY")
        activity.log(self.app_id, "SUBMIT_UNVERIFIED", evidence)
        say(f"\nSUBMIT CLICKED BUT NOT VERIFIED: {evidence}")
        say("Check the browser and your inbox. The harness will not resubmit this application.")
        return 13

    def fail(self, e: Exception) -> int:
        if self.clicked:
            return self._record_unverified(f"submit was clicked, then: {e}")
        if isinstance(e, StopRequested):
            self._update(notes="Halted by /stop; nothing submitted.")
            say(f"\nHALTED: {e} Nothing was submitted.")
            return 11
        if isinstance(e, Halt):
            self._update(notes=e.note)
            activity.log(self.app_id, "SUBMIT_HALTED", e.note)
            say(f"\n{e.note}")
            return e.code
        if self.page is not None:
            checkpoint(self.app_id, "error", {"error": repr(e), "url": self.page.url})
            screenshot(self.page, self.app_id, "error")
        self._update(status="FAILED", error_reason=repr(e), next_action="RETRY")
        activity.log(self.app_id, "FAILED", repr(e))
        say(f"\nFAILED before submitting: {e!r}. Nothing was submitted; /retry {self.app_id} to try again.")
        return 1

    # ------------------------------------------------------------ helpers

    def _ask(self, stage: str, payload: dict) -> str | None:
        nonce = gate.open_prompt(self.app_id, stage, payload)
        try:
            return gate.wait(self.app_id, nonce, self.timeout, self.poll)
        finally:
            gate.close_prompt(self.app_id)

    def _settle(self, ms: int = 10000) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=ms)
        except Exception:
            pass

    def _clear_challenges(self) -> None:
        """Hand every CAPTCHA / MFA / OTP to the user; never bypass one."""
        for _ in range(5):
            reason = safety.detect(self.page, self.dismissed.get(self.page.url, set()))
            if not reason:
                return
            checkpoint(self.app_id, "challenge", {"reason": reason, "url": self.page.url})
            screenshot(self.page, self.app_id, "challenge")
            if self.headless:
                raise Halt(14, f"Stopped at a challenge ({reason}); headless, so it can't be handed to you. "
                               "Nothing was submitted.")
            say("\nUSER TAKEOVER NEEDED")
            say(reason)
            say("Solve it yourself in the browser window (the harness never bypasses CAPTCHA/MFA/OTP), "
                "then reply CONTINUE — or NO to stop.")
            url = self.page.url
            if self._ask("takeover", {"reason": reason, "url": url}) != "CONTINUE":
                raise Halt(14, "Stopped at a CAPTCHA/MFA/OTP challenge. Nothing was submitted.")
            if reason.startswith(safety.TEXT_REASON_PREFIX):
                # The user looked and says the page is fine: don't re-ask
                # about the same wording (e.g. a job description) on this page.
                self.dismissed.setdefault(url, set()).add(reason)
            self._settle()
        raise Halt(14, "A challenge is still showing after 5 hand-offs. Nothing was submitted.")

    # ------------------------------------------------------------ flow

    def drive(self) -> int:
        say(f"Submitting {self.app_id}: {self.app.get('company')} — {self.app.get('role')} "
            f"(ats: {self.adapter.NAME})")
        activity.log(self.app_id, "SUBMIT_START", f"ats={self.adapter.NAME}")
        if self.adapter.MANUAL:
            return self._manual()
        self._open_form()
        result = self._fill()
        shot = screenshot(self.page, self.app_id, "pre_submit")
        checkpoint(self.app_id, "pre_submit", {"url": self.page.url, "rows": [r.__dict__ for r in result.rows]})
        self._print_ready(result.rows, shot)
        self._approve()
        return self._submit()

    def _open_form(self) -> None:
        page = self.page
        for url in self.adapter.form_urls(self.app):
            if not url:
                continue
            check_stop()
            page.goto(url, wait_until="domcontentloaded")
            self._settle()
            self._clear_challenges()
            if form.has_form(page):
                return
            embedded = page.evaluate(_EMBEDDED_ATS_JS)
            if embedded:
                page.goto(embedded, wait_until="domcontentloaded")
                self._settle()
                self._clear_challenges()
                if form.has_form(page):
                    return
            if form.click_apply_button(page):
                self._settle()
                self._clear_challenges()
                if form.has_form(page):
                    return
        if self.headless:
            raise Halt(14, "Couldn't find the application form. Nothing was submitted.")
        say("\nCouldn't find the application form automatically. Open it in the browser window, "
            "then reply CONTINUE — or NO to stop.")
        if self._ask("takeover", {"reason": "application form not found", "url": page.url}) != "CONTINUE" \
                or not form.has_form(page):
            raise Halt(14, "Application form not found. Nothing was submitted.")

    def _fill(self) -> form.FormResult:
        accept_blank = False
        sources: dict[str, str] = {}
        while True:
            check_stop()
            self._clear_challenges()
            result = form.fill_form(self.page, self.profile, self.rules, self.resume,
                                    accept_blank=accept_blank, sources=sources)
            checkpoint(self.app_id, "filled", {"url": self.page.url, "unresolved": result.unresolved})
            if not result.unresolved:
                return result
            say("\nNEEDS YOUR INPUT")
            say("These fields have no pre-approved answer (the harness never guesses):")
            for u in result.unresolved:
                say(f"  - [{'required' if u['required'] else 'optional'}] {u['question']} — {u['reason']}")
            where = ("add answers to messages/screening-answers.yaml" if self.headless else
                     "answer them in the browser window, or add answers to messages/screening-answers.yaml")
            say(f"Please {where}, then reply CONTINUE (empty optional fields will stay blank) — or NO to stop.")
            if self._ask("input", {"questions": result.unresolved}) != "CONTINUE":
                raise Halt(14, "Stopped at unanswered questions. Nothing was submitted.")
            accept_blank = True
            self.rules = answers_mod.load()  # pick up answers added meanwhile

    def _print_ready(self, rows: list[form.Row], shot: Path | None) -> None:
        app = self.app
        say("\nAPPLICATION READY")
        say(f"Application: {self.app_id}")
        say(f"Company: {app.get('company')}")
        say(f"Role: {app.get('role')}")
        say(f"Match: {app.get('match_score')}%")
        say(f"Form: {self.page.url}")
        say(f"Resume: {(app.get('resume_type') or 'master').upper()} — {self.resume.name}")
        say(f"Answers ({len(rows)}):")
        for r in rows:
            say(f"  - {r.label or '(unlabelled)'}: {r.value}   [{r.source}]")
        if shot:
            say(f"Screenshot: {shot}")

    def _approve(self) -> None:
        ms = modes.status(Config.load())
        if ms.effective == "autonomous":
            say("Mode: autonomous (policy + submission + session locks all set) — submitting without asking.")
            activity.log(self.app_id, "APPROVED", "autonomous mode")
            return
        minutes = max(1, round(self.timeout / 60))
        say(f"Mode: supervised — your explicit YES is required.")
        say(f"Approve? YES / NO   (silence is NO; this prompt expires in {minutes} min)")
        decision = self._ask("approval", {"company": self.app.get("company"), "role": self.app.get("role")})
        if decision == "YES":
            activity.log(self.app_id, "APPROVED", "user YES")
            return
        if decision == "NO":
            self._update(status="DECLINED", next_action=None)
            activity.log(self.app_id, "DECLINED", "user NO at approval gate")
            raise Halt(12, "Declined by you. Nothing was submitted.")
        raise Halt(12, f"No answer within {minutes} min — silence is NO. Nothing was submitted.")

    def _submit(self) -> int:
        check_stop()
        if _applied_today(_load_apps()) >= self.cfg.max_per_day:
            raise Halt(10, "Daily cap reached while waiting. Nothing was submitted.")
        self._clear_challenges()
        button = form.find_submit(self.page)
        if button is None:
            raise Halt(14, "Couldn't find the submit button. Nothing was submitted.")
        before_text, before_url = form.page_text(self.page), self.page.url
        self.clicked = True
        checkpoint(self.app_id, "submit_clicked", {"url": before_url})
        button.click()
        self._settle(20000)
        self._clear_challenges()  # e.g. an invisible reCAPTCHA escalating after submit
        ok, evidence = form.confirmation(self.page, before_text, before_url)
        screenshot(self.page, self.app_id, "post_submit")
        checkpoint(self.app_id, "post_submit", {"url": self.page.url, "verified": ok, "evidence": evidence})
        return self._record_applied(evidence, "the harness") if ok else self._record_unverified(evidence)

    def _manual(self) -> int:
        page = self.page
        page.goto(self.app.get("job_url"), wait_until="domcontentloaded")
        self._settle()
        if self.headless:
            raise Halt(14, f"{self.adapter.REASON} It needs a visible browser. Nothing was submitted.")
        before_text, before_url = form.page_text(page), page.url
        say(f"\nMANUAL APPLICATION: {self.adapter.REASON}")
        say("Fill in and submit the application yourself in the browser window. Reply CONTINUE once "
            "the confirmation page is showing — or NO to stop.")
        if self._ask("takeover", {"reason": "manual application", "url": page.url}) != "CONTINUE":
            raise Halt(14, "Stopped. Nothing was recorded as submitted.")
        ok, evidence = form.confirmation(page, before_text, before_url)
        if ok:
            return self._record_applied(evidence, "you in the browser")
        self.clicked = True  # the user says they submitted; we couldn't confirm it
        return self._record_unverified(f"you reported submitting, but {evidence}")
