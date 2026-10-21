import sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from fastapi.testclient import TestClient
from main import app
from backend import deps
from backend.search import SearchUnavailable


class FakeJobs:
    def __init__(self): self.calls = []
    def run_publish(self, ids): self.calls.append(("publish", list(ids))); return 101
    def run_reset(self): self.calls.append(("reset",)); return 102
    def run_inject(self, t): self.calls.append(("inject", t)); return 103
    def reset_state(self, run_id): return {"run_id": run_id, "life_cycle_state": "TERMINATED"} if run_id == 102 else None


class FakeReads:
    def prompt_rows(self): return [{"prompt_id": "q001"}]
    def prompt_detail(self, pid): return {"prompt_id": pid, "answers": []} if pid == "q001" else None
    def prompt_suggestions(self): return [{"suggestion_id": "c001"}]


class FakeRepo:
    def quarantine_points(self):
        return {"count": 1, "rule_id": "EX-03", "points": [{"enforcement_point": "ingest", "occurred_at": "2026-10-21T08:00:00Z"}]}
    def tier_counts(self): return {"T0": 3, "T2": 1}


c = TestClient(app)


@pytest.fixture(autouse=True)
def fakes():
    """Fresh fakes per test, set here and restored on teardown (never module-level overrides)."""
    J, R, F = FakeJobs(), FakeReads(), FakeRepo()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.update({deps.get_jobs: lambda: J, deps.get_reads: lambda: R, deps.get_fix_repo: lambda: F})
    yield J, R, F
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_inject_validates_truth():
    assert c.post("/api/demo/inject/S4_repost").status_code == 202
    assert c.post("/api/demo/inject/S4_exclusion").status_code == 404
    assert c.post("/api/demo/inject/not_a_truth").status_code == 404


def test_reset():
    assert c.post("/api/demo/reset").json() == {"run_id": 102}


def test_reset_status():
    assert c.get("/api/demo/reset/102").json()["life_cycle_state"] == "TERMINATED"
    assert c.get("/api/demo/reset/999").status_code == 404


def test_jobs_reset_state_unknown_run_is_none(monkeypatch):
    from types import SimpleNamespace as N
    from backend.jobs import Jobs
    monkeypatch.setenv("RESET_JOB_ID", "7")
    def get_run(run_id):
        if run_id == 1: raise RuntimeError("does not exist")
        return N(job_id=7 if run_id == 2 else 8, state=N(life_cycle_state=N(value="TERMINATED"), result_state=N(value="SUCCESS")))
    j = Jobs(N(jobs=N(get_run=get_run)))
    assert j.reset_state(1) is None and j.reset_state(3) is None
    assert j.reset_state(2) == {"run_id": 2, "life_cycle_state": "TERMINATED", "result_state": "SUCCESS"}


def test_jobs_run_publish_sends_the_comma_list(monkeypatch):
    from types import SimpleNamespace as N
    from backend.jobs import Jobs
    monkeypatch.setenv("PUBLISH_JOB_ID", "5")
    sent = []
    j = Jobs(N(jobs=N(run_now=lambda job_id, job_parameters: sent.append((job_id, job_parameters)) or N(run_id=9))))
    assert j.run_publish(["fx_a", "fx_b"]) == 9 and sent == [(5, {"fix_ids": "fx_a,fx_b"})]


def test_prompt_routes():
    assert c.get("/api/prompts").json() == [{"prompt_id": "q001"}]
    assert c.get("/api/prompts/q001").json()["prompt_id"] == "q001"
    r = c.get("/api/prompts/q999")
    assert r.status_code == 404 and r.json()["detail"] == "Unknown prompt"
    assert c.get("/api/prompt-suggestions").json() == [{"suggestion_id": "c001"}]


def test_search_route_errors():
    class Boom:
        def __init__(self, e): self.e = e
        def search(self, q): raise self.e
    app.dependency_overrides[deps.get_search] = lambda: Boom(ValueError("Type a question to search."))
    r = c.get("/api/search?q=%20")
    assert r.status_code == 400 and r.json()["detail"] == "Type a question to search."
    app.dependency_overrides[deps.get_search] = lambda: Boom(SearchUnavailable("vs down"))
    r = c.get("/api/search?q=pizza")
    assert r.status_code == 503 and r.json()["detail"] == "Search is unavailable right now."


def test_quarantine_never_returns_text():
    body = c.get("/api/quarantine").json()
    assert set(body) == {"count", "rule_id", "reason", "points"}
    assert body["count"] == 1 and body["reason"] == "No sports betting association"
    assert set(body["points"][0]) == {"enforcement_point", "occurred_at"}


def test_fix_summary_shape():
    assert c.get("/api/fix/summary").json() == {"tiers": {"T0": {"ready": 3}, "T1": {"to_review": 0}, "T2": {"to_review": 1}},
                                                "quarantined": 1, "review_mode": True}


def test_genie_none_means_not_configured(monkeypatch):
    monkeypatch.setenv("GENIE_SPACE_ID", "none")
    app.dependency_overrides.pop(deps.get_genie, None)
    assert c.post("/api/genie/ask", json={"question": "hi"}).status_code == 503


def test_supervisor_route_is_gone():
    assert c.post("/api/ask", json={"question": "hi"}).status_code in (404, 405)


def test_v2_routes_are_gone():
    for path in ("/api/suggestions", "/api/opportunities", "/api/signals"):
        assert c.get(path).status_code in (404, 405), path
