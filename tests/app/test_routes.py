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
