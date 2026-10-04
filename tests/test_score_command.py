from harness import cli, paths
from harness.state import read_json, write_json

FRONTEND = {
    "job_hash": "fe1", "company": "acme", "role": "Frontend Engineer", "location": "Remote",
    "job_url": "https://example.com/fe1",
    "description": "React, TypeScript and Next.js; design system, code reviews, unit tests.",
}
OFF_TARGET = {
    "job_hash": "mm1", "company": "acme", "role": "Market Manager", "location": "Gurugram, India",
    "job_url": "https://example.com/mm1", "description": "Travel CRM growth.",
}


def test_rescoring_moves_jobs_between_buckets_and_never_duplicates(capsys):
    write_json(paths.DISCOVERED_JOBS, [FRONTEND, OFF_TARGET])
    # Stale state from the old scorer: the off-target job sits in qualified.
    write_json(paths.QUALIFIED_JOBS, [dict(OFF_TARGET, match_score=80)])
    write_json(paths.REJECTED_JOBS, [])

    assert cli.main(["score"]) == 0

    qualified = {j["job_hash"] for j in read_json(paths.QUALIFIED_JOBS, [])}
    rejected = {j["job_hash"]: j for j in read_json(paths.REJECTED_JOBS, [])}
    assert qualified == {"fe1"}
    assert set(rejected) == {"mm1"}
    assert rejected["mm1"]["filter_reasons"]
    assert rejected["mm1"]["score_rationale"].startswith("Filtered:")
    assert "1 failed hard filters" in capsys.readouterr().out
