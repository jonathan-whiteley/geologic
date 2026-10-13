import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from fastapi.testclient import TestClient
from main import app
from backend import deps

class FakeSuggestions:
    def __init__(self):
        self.rows = {"s1": {"suggestion_id": "s1", "state": "pending_review", "tier": "T1"}}
        self.runs = {}
    def list(self): return list(self.rows.values())
    def claim(self, sid, reviewer):
        r = self.rows.get(sid)
        if r and r["state"] == "pending_review" and r["tier"] in ("T1", "T2"):
            r["state"] = "publishing"; return True
        return False
    def set_run(self, sid, run_id): self.runs[sid] = run_id
    def release(self, sid, error):
        r = self.rows.get(sid)
        if r and r["state"] == "publishing":
            r["state"], r["error"] = "pending_review", error; return True
        return False
    def reject(self, sid, reviewer):
        r = self.rows.get(sid)
        if r and r["state"] == "pending_review":
            r["state"] = "rejected"; return True
        return False
    def status(self, sid): return {"state": self.rows[sid]["state"], "publish_step": 0, "error": None, "prompt_ids": []}

class FakeJobs:
    def __init__(self): self.calls = []
    def run_publish(self, sid): self.calls.append(("publish", sid)); return 101
    def run_reset(self): self.calls.append(("reset",)); return 102
    def run_inject(self, t): self.calls.append(("inject", t)); return 103
    def reset_state(self, run_id): return {"run_id": run_id, "life_cycle_state": "TERMINATED"} if run_id == 102 else None

S, J = FakeSuggestions(), FakeJobs()
app.dependency_overrides[deps.get_suggestions] = lambda: S
app.dependency_overrides[deps.get_jobs] = lambda: J
c = TestClient(app)

def test_approve_twice_second_is_409():  # Review Focus 3
    assert c.post("/api/suggestions/s1/approve").status_code == 202
    assert c.post("/api/suggestions/s1/approve").status_code == 409
    assert J.calls.count(("publish", "s1")) == 1 and S.runs["s1"] == 101

def test_reject_after_publish_start_is_409():
    assert c.post("/api/suggestions/s1/reject").status_code == 409

def test_inject_validates_truth():
    assert c.post("/api/demo/inject/S3_goff").status_code == 202
    assert c.post("/api/demo/inject/not_a_truth").status_code == 404

def test_reset():
    assert c.post("/api/demo/reset").json() == {"run_id": 102}

class FakeReads:
    def prompt_search(self, q): return "q002" if "pizza" in q else None
    def track_prompt(self, pid, user): return pid == "c001"
    def prompt_explorer(self, pid): return None

app.dependency_overrides[deps.get_reads] = lambda: FakeReads()

def test_prompt_search_validation():
    assert c.get("/api/prompts/search?q=%20").status_code == 400
    assert c.get("/api/prompts/search?q=zzz").status_code == 404
    assert c.get("/api/prompts/search?q=pizza%20party").json() == {"prompt_id": "q002"}

def test_track_unknown_is_404():
    assert c.post("/api/prompts/c001/track").json() == {"tracked": True}
    assert c.post("/api/prompts/nope/track").status_code == 404

def test_reset_status():
    assert c.get("/api/demo/reset/102").json()["life_cycle_state"] == "TERMINATED"
    assert c.get("/api/demo/reset/999").status_code == 404

def test_approve_releases_row_when_job_fails_to_start():  # finding 2
    S.rows["s2"] = {"suggestion_id": "s2", "state": "pending_review", "tier": "T1"}
    orig = J.run_publish
    def boom(sid): raise RuntimeError("jobs api down")
    J.run_publish = boom
    try:
        r = c.post("/api/suggestions/s2/approve")
    finally:
        J.run_publish = orig
    assert r.status_code == 502 and "Try again" in r.json()["detail"]
    assert S.rows["s2"]["state"] == "pending_review" and "s2" not in S.runs
    assert c.post("/api/suggestions/s2/approve").status_code == 202  # Approve works again


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


FakeReads.prompt_inventory = lambda self: [{"prompt_id": "q001"}]
FakeReads.opportunity_evidence = lambda self, oid: None if oid == "nope" else {"opp_id": oid, "page_id": "pg_menu", "wrong_claims": [],
                                                                                "truth": None, "cited_instead": [], "signal": None}

def test_prompt_inventory_route():
    assert c.get("/api/prompts").json() == [{"prompt_id": "q001"}]

def test_evidence_route():
    assert c.get("/api/opportunities/nope/evidence").status_code == 404
    assert c.get("/api/opportunities/opp_1/evidence").json()["opp_id"] == "opp_1"
