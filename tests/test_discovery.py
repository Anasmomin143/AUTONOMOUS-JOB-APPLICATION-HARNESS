import httpx

from harness import discovery
from harness.config import Config
from harness.discovery import greenhouse


def _raw(n: int, role: str = "Frontend Engineer", location: str = "Remote") -> dict:
    return {"company": "acme", "role": role, "job_url": f"https://example.com/{n}", "location": location}


def test_duplicates_and_off_target_jobs_do_not_use_up_the_count(monkeypatch):
    raw = [_raw(0), _raw(1, role="Data Scientist"), _raw(2), _raw(3), _raw(4)]
    monkeypatch.setattr(discovery, "SOURCES", {"fake": lambda cfg, warnings: raw})

    jobs, warnings, skipped = discovery.discover_all(Config.load(), 2, seen={"https://example.com/0"})

    assert [j["job_url"] for j in jobs] == ["https://example.com/2", "https://example.com/3"]
    assert skipped == {"duplicate": 1, "filtered": 1}
    assert warnings == []


def test_failing_source_does_not_stop_the_next_one(monkeypatch):
    def boom(cfg, warnings):
        raise RuntimeError("down")

    monkeypatch.setattr(discovery, "SOURCES", {"bad": boom, "good": lambda cfg, warnings: [_raw(1)]})

    jobs, warnings, _ = discovery.discover_all(Config.load(), 10)

    assert len(jobs) == 1
    assert warnings and warnings[0].startswith("bad:")


def test_greenhouse_skips_only_the_failing_company(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "/boards/broken/" in request.url.path:
            raise httpx.ConnectError("blocked", request=request)
        return httpx.Response(200, json={"jobs": [{
            "id": 7, "title": "Frontend Engineer", "absolute_url": "https://example.com/gh7",
            "location": {"name": "Remote"}, "content": "<p>React</p>",
        }]})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))

    warnings: list[str] = []
    jobs = greenhouse.fetch(Config.load(), warnings)

    assert [j["job_url"] for j in jobs] == ["https://example.com/gh7"]
    assert len(warnings) == 1 and warnings[0].startswith("greenhouse/broken:")
