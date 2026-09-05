"""ATS-specific application adapters."""
from __future__ import annotations
from typing import Callable

from . import greenhouse, lever, workday, linkedin_easy, generic_form


def pick_adapter(url: str) -> tuple[str, Callable]:
    u = (url or "").lower()
    if "greenhouse.io" in u or "boards.greenhouse.io" in u:
        return "greenhouse", greenhouse.apply
    if "lever.co" in u:
        return "lever", lever.apply
    if "myworkdayjobs" in u or "workday" in u:
        return "workday", workday.apply
    if "linkedin.com/jobs" in u:
        return "linkedin", linkedin_easy.apply
    return "generic", generic_form.apply
