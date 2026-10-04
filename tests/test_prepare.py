import datetime as dt

from harness import batch, cli, paths
from harness.state import read_json, write_json

JOB = {
    "job_hash": "fe1", "company": "acme", "role": "Frontend Engineer", "location": "Remote",
    "job_url": "https://example.com/fe1", "requisition_id": "R-1", "match_score": 88,
}


def _apps() -> list[dict]:
    return read_json(paths.APPLICATIONS_JSON, {"applications": []})["applications"]


def _seed(*jobs: dict) -> None:
    write_json(paths.QUALIFIED_JOBS, list(jobs))


def _add_master_resume() -> None:
    paths.MASTER_RESUME_PDF.write_bytes(b"%PDF-1.4 test\n")


def test_missing_master_resume_is_refused_and_nothing_recorded(capsys):
    _seed(JOB)
    assert cli.main(["prepare", "--job-id", "fe1"]) == 8
    assert _apps() == []
    assert "master resume not found" in capsys.readouterr().out


def test_preparing_the_same_job_twice_is_refused(capsys):
    _seed(JOB)
    _add_master_resume()
    assert cli.main(["prepare", "--job-id", "fe1"]) == 0
    assert cli.main(["prepare", "--job-id", "fe1"]) == 7
    assert len(_apps()) == 1
    assert "already prepared" in capsys.readouterr().out


def test_same_company_and_role_under_a_new_url_is_a_duplicate():
    repost = dict(JOB, job_hash="fe2", job_url="https://example.com/fe1-repost", requisition_id="R-2")
    _seed(JOB, repost)
    _add_master_resume()
    assert cli.main(["prepare", "--job-id", "fe1"]) == 0
    assert cli.main(["prepare", "--job-id", "fe2"]) == 7
    assert len(_apps()) == 1


def test_decline_only_applies_before_submission(capsys):
    write_json(paths.APPLICATIONS_JSON, {"applications": [
        {"application_id": "APP-1", "status": "READY_FOR_APPROVAL"},
        {"application_id": "APP-2", "status": "APPLIED"},
    ]})
    assert cli.main(["decline", "--app-id", "APP-1", "--reason", "off-target"]) == 0
    assert cli.main(["decline", "--app-id", "APP-2", "--reason", "changed my mind"]) == 9
    apps = {a["application_id"]: a for a in _apps()}
    assert apps["APP-1"]["status"] == "DECLINED" and "Declined by user: off-target" in apps["APP-1"]["notes"]
    assert apps["APP-2"]["status"] == "APPLIED"


def test_ids_continue_after_recorded_applications_when_counters_are_missing():
    # state/counters.json is gitignored, so a fresh clone has no counters
    # but applications.json already holds IDs.
    year, day = dt.date.today().year, dt.date.today().isoformat()
    write_json(paths.APPLICATIONS_JSON, {"applications": [
        {"application_id": f"APP-{year}-0007", "batch_id": f"BATCH-{day}-004"},
    ]})
    assert not paths.COUNTERS_JSON.exists()
    assert batch.mint_application_id() == f"APP-{year}-0008"
    assert batch.mint_batch_id() == f"BATCH-{day}-005"
