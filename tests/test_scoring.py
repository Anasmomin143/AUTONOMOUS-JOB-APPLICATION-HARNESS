from harness.config import Config
from harness.profile import load_profile
from harness.scoring import extract_required_years, score_job


def _score(role: str, description: str):
    return score_job({"role": role, "description": description}, Config.load(), load_profile())


def test_job_naming_no_tracked_skills_earns_no_skill_points():
    s = _score("Barista", "Make great coffee for our guests. Next steps: apply today!")
    assert s.breakdown["technical_skills"] == 0
    assert s.breakdown["ats_keyword_alignment"] == 0
    assert s.total < 70


def test_frontend_job_qualifies():
    s = _score(
        "Senior Frontend Engineer",
        "4+ years of experience with React, TypeScript and Next.js. Own our design "
        "system, code reviews and unit tests in Jest for a travel booking platform.",
    )
    assert s.breakdown["technical_skills"] == 30
    assert s.total >= 80


def test_skill_owned_inside_longer_profile_entry():
    # Profile lists "Angular v14–v17 (incl. Signals, …)" and "Tailwind CSS".
    s = _score("Frontend Engineer (Angular)", "Angular, RxJS and Tailwind.")
    assert {"angular", "tailwind"} <= set(s.matched["skills"])
    assert s.missing["skills"] == ["rxjs"]


def test_unowned_skill_is_missing():
    s = _score("Frontend Engineer", "Vue and React.")
    assert s.matched["skills"] == ["react"]
    assert s.missing["skills"] == ["vue"]


def test_profile_skill_parsing_handles_parentheses_and_wrapped_lines():
    skills = load_profile().skills
    assert "Angular v14–v17" in skills
    assert "Standalone Components)" not in skills
    assert "Core Web Vitals" in skills  # from the wrapped continuation line


def test_required_years_needs_experience_context():
    assert extract_required_years("Founded 20 years ago. 3-5 years of experience required.") == 3
    assert extract_required_years("We have grown for 20 years.") is None
    assert extract_required_years("5+ years' hands-on experience") == 5


def test_seniority_ignores_substrings_and_prose():
    weight = Config.load().scoring["weights"]["seniority"]
    # "Internal" is not "intern"; "senior leadership" in prose is not the title.
    s = _score("Frontend Engineer, Internal Tools", "Report to our senior leadership. React.")
    assert s.breakdown["seniority"] == weight
    junior = _score("Junior Frontend Engineer", "React.")
    assert junior.breakdown["seniority"] < weight
