"""Detect CAPTCHA / MFA / OTP / anti-bot challenges and stop cleanly.

Only *visible, interactive* challenges count. Many ATS forms (Greenhouse
among them) load an invisible reCAPTCHA and print "protected by
reCAPTCHA" in the footer on every page; treating that as a challenge
would halt every application. When an invisible check escalates to a
real challenge, its frame becomes visible and is caught here.
"""
from __future__ import annotations
import re

# Prompt phrasing only. Bare "MFA", "OTP" or "two-factor" show up in job
# descriptions ("build MFA login flows") and must not halt a run; real OTP
# fields are caught by the selectors below.
TEXT_REASON_PREFIX = "Page text suggests"
_CHALLENGE_TEXT_RX = re.compile(
    r"(?i)\b(verify (that )?you('| a)re (a )?human|i'?m not a robot|prove you'?re human|"
    r"unusual (activity|traffic)|security check|one[- ]?time (password|passcode|code)|"
    r"enter (the |your )?(\d[- ]digit |verification |security |one[- ]?time )?code)\b"
)

_CHALLENGE_SELECTORS = [
    "iframe[src*='recaptcha/api2/bframe']",            # reCAPTCHA image challenge
    "iframe[src*='recaptcha/enterprise/bframe']",
    "iframe[title='reCAPTCHA']:not(.grecaptcha-badge iframe)",  # v2 checkbox
    "iframe[src*='hcaptcha.com'][src*='frame=challenge']",
    "iframe[src*='hcaptcha.com'][src*='frame=checkbox']",
    "iframe[src*='challenges.cloudflare.com']",
    "div#px-captcha",
    "input[name*='otp' i]",
    "input[autocomplete='one-time-code']",
]


def _visible(el) -> bool:
    try:
        if not el.is_visible():
            return False
        box = el.bounding_box()
        return bool(box) and box["width"] > 10 and box["height"] > 10
    except Exception:
        return False


def detect(page, dismissed: set[str] = frozenset()) -> str | None:
    """A human-readable reason if a challenge is showing, else None.
    Text-only reasons in `dismissed` (the user already said the page is
    fine) are skipped; a visible challenge element never is."""
    for sel in _CHALLENGE_SELECTORS:
        try:
            if any(_visible(el) for el in page.query_selector_all(sel)):
                return f"Detected challenge element: {sel}"
        except Exception:
            continue
    try:
        text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")
    except Exception:
        text = ""
    for m in _CHALLENGE_TEXT_RX.finditer(text or ""):
        reason = f"{TEXT_REASON_PREFIX} a CAPTCHA / MFA / OTP prompt ({m.group(0)!r})."
        if reason not in dismissed:
            return reason
    return None
