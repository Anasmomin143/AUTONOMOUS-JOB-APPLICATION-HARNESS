"""Pre-approved screening answers from messages/screening-answers.yaml."""
from __future__ import annotations
import re

import yaml

from ..paths import SCREENING_ANSWERS

STOP_FOR_USER = "__STOP_FOR_USER__"


def load() -> list[tuple[re.Pattern, str]]:
    """(pattern, answer) rules in file order; the first match wins."""
    if not SCREENING_ANSWERS.exists():
        return []
    data = yaml.safe_load(SCREENING_ANSWERS.read_text(encoding="utf-8")) or {}
    rules: list[tuple[re.Pattern, str]] = []
    for i, entry in enumerate(data.get("answers") or []):
        try:
            rules.append((re.compile(str(entry["match"])), str(entry["answer"])))
        except (KeyError, TypeError, re.error) as e:
            raise ValueError(f"screening-answers.yaml entry #{i + 1} is invalid: {e}") from e
    return rules


def match(question: str, rules: list[tuple[re.Pattern, str]]) -> str | None:
    for rx, answer in rules:
        if rx.search(question):
            return answer
    return None
