from harness.profile import load_profile
from harness.resume import tailor, validate

JOB = {"role": "Senior Frontend Engineer (React)", "description": "React, TypeScript, Next.js"}


def test_tailored_resume_built_from_profile_validates():
    # Regression: the proper-noun check used to match across line breaks
    # ("Jordan Example\nPune") and rejected every tailored resume.
    profile = load_profile()
    result = validate.validate(tailor.tailor(JOB, profile).markdown, profile)
    assert result.ok, result.problems


def test_fabricated_metric_and_employer_are_rejected():
    profile = load_profile()
    md = tailor.tailor(JOB, profile).markdown + "\n- Grew revenue 300% at Google Cloud Platform.\n"
    problems = validate.validate(md, profile).problems
    assert "Metric not in master profile: '300%'" in problems
    assert "Possible fabricated proper noun: 'Google Cloud Platform'" in problems
