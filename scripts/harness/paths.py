"""Resolves all filesystem paths relative to the harness root."""
from __future__ import annotations
import os
from pathlib import Path


def root() -> Path:
    env = os.environ.get("HARNESS_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    # Fallback: two levels up from this file (…/scripts/harness/paths.py).
    return Path(__file__).resolve().parents[2]


R = root()

CONFIG_DIR       = R / "config"
PROFILE_DIR      = R / "profile"
JOBS_DIR         = R / "jobs"
APPLICATIONS_DIR = R / "applications"
RESUMES_DIR      = R / "resumes"
MESSAGES_DIR     = R / "messages"
TRACKER_DIR      = R / "tracker"
REPORTS_DIR      = R / "reports"
STATE_DIR        = R / "state"

SETTINGS_YAML          = CONFIG_DIR / "settings.yaml"
SCORING_YAML           = CONFIG_DIR / "scoring.yaml"
AUTOMATION_POLICY_YAML = CONFIG_DIR / "automation-policy.yaml"

MASTER_PROFILE_MD  = PROFILE_DIR / "master-profile.md"
MASTER_RESUME_PDF  = PROFILE_DIR / "master-resume.pdf"
LINKEDIN_MD        = PROFILE_DIR / "linkedin.md"
PREFERENCES_MD     = PROFILE_DIR / "preferences.md"
SCREENING_ANSWERS  = MESSAGES_DIR / "screening-answers.yaml"

DISCOVERED_JOBS = JOBS_DIR / "discovered.json"
QUALIFIED_JOBS  = JOBS_DIR / "qualified.json"
REJECTED_JOBS   = JOBS_DIR / "rejected.json"
ARCHIVE_JOBS    = JOBS_DIR / "archive.json"

APPLICATIONS_JSON = APPLICATIONS_DIR / "applications.json"
FOLLOWUPS_JSON    = APPLICATIONS_DIR / "followups.json"
INTERVIEWS_JSON   = APPLICATIONS_DIR / "interviews.json"

EXCEL_TRACKER  = TRACKER_DIR / "Job_Application_Tracker.xlsx"
ACTIVITY_LOG   = TRACKER_DIR / "activity_log.md"

STOP_SENTINEL   = STATE_DIR / "STOP"
MODE_LOG        = STATE_DIR / "mode-log.md"
MODE_STATE      = STATE_DIR / "mode.json"
COUNTERS_JSON   = STATE_DIR / "counters.json"
DAILY_COUNTER   = STATE_DIR / "daily-count.json"


def app_dir(app_id: str) -> Path:
    return APPLICATIONS_DIR / app_id


def ensure_dirs() -> None:
    for d in (
        CONFIG_DIR, PROFILE_DIR, JOBS_DIR, APPLICATIONS_DIR,
        RESUMES_DIR, RESUMES_DIR / "master", RESUMES_DIR / "tailored",
        MESSAGES_DIR, MESSAGES_DIR / "recruiters", MESSAGES_DIR / "followups",
        TRACKER_DIR, REPORTS_DIR, REPORTS_DIR / "daily", REPORTS_DIR / "weekly",
        STATE_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
