import pytest

from harness import filters
from harness.config import Config


def _reasons(**job):
    return filters.reasons(job, Config.load())


def test_on_target_job_passes():
    assert _reasons(role="Senior Frontend Engineer", company="acme", location="Bengaluru, India") == []


def test_empty_location_is_not_disqualifying():
    assert _reasons(role="React Developer", company="acme", location="") == []


@pytest.mark.parametrize("job, expected", [
    ({"role": "Data Scientist", "location": "Remote"}, "target_role_patterns"),
    ({"role": "Staff Frontend Engineer", "location": "Remote"}, "title_blocklist"),
    ({"role": "Frontend Engineer", "location": "Brazil"}, "allowed_locations"),
    ({"role": "Frontend Engineer", "location": "Remote", "company": "BlockedCo"}, "company_blocklist"),
    ({"role": "Frontend Engineer", "location": "Remote",
      "description": "10+ years of professional experience."}, "max_experience_years"),
])
def test_off_target_job_is_rejected_with_reason(job, expected):
    reasons = filters.reasons(job, Config.load())
    assert any(expected in r for r in reasons), reasons
