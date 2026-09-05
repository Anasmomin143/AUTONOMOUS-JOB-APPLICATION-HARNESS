"""Detect CAPTCHA / MFA / OTP / anti-bot challenges and stop cleanly."""
from __future__ import annotations
import re

_CHALLENGE_TEXT_RX = re.compile(
    r"(?i)(captcha|recaptcha|hcaptcha|verify.*(human|not.a.robot)|"
    r"one[- ]?time (password|code)|otp|two[- ]?factor|mfa|"
    r"security check|prove.you'?re.human|access.denied|"
    r"unusual (activity|traffic))"
)

_CHALLENGE_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[title*='captcha']",
    "iframe[src*='hcaptcha']",
    "div#px-captcha",
    "input[name*='otp' i]",
    "input[autocomplete='one-time-code']",
]


async def detect(page) -> str | None:
    """Returns a human-readable reason if a challenge is present, else None."""
    for sel in _CHALLENGE_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                return f"Detected challenge element: {sel}"
        except Exception:
            continue
    try:
        text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")
    except Exception:
        text = ""
    if text and _CHALLENGE_TEXT_RX.search(text):
        return "Page text suggests a CAPTCHA / MFA / OTP prompt."
    return None
