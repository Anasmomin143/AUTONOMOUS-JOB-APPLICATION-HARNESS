"""Load YAML configuration with fail-safe fallbacks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import yaml

from .paths import SETTINGS_YAML, SCORING_YAML, AUTOMATION_POLICY_YAML


def _load(path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class Config:
    settings: dict[str, Any]
    scoring: dict[str, Any]
    policy: dict[str, Any]

    @classmethod
    def load(cls) -> "Config":
        return cls(
            settings=_load(SETTINGS_YAML),
            scoring=_load(SCORING_YAML),
            policy=_load(AUTOMATION_POLICY_YAML),
        )

    # Policy helpers ---------------------------------------------------

    @property
    def mode(self) -> str:
        return str(self.policy.get("mode", "supervised")).lower()

    @property
    def submission_allowed(self) -> bool:
        return bool(self.policy.get("allow_application_submission", False))

    @property
    def min_score(self) -> int:
        return int(self.policy.get("minimum_match_score", 85))

    @property
    def max_per_batch(self) -> int:
        return int(self.policy.get("max_applications_per_batch", 100))

    @property
    def max_per_day(self) -> int:
        return int(self.policy.get("max_applications_per_day", 100))
