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


class ProofSuggestions(FakeSuggestions):
    def __init__(self, fail=False):
        super().__init__(); self.saved = []; self.fail = fail
        self.rows["p1"] = {"suggestion_id": "p1", "state": "published", "tier": "T1", "title": "Fix price", "prompt_ids": ["q001"]}
    def status(self, sid):
        r = self.rows[sid]; return {"state": r["state"], "publish_step": 5, "error": None, "prompt_ids": r.get("prompt_ids", [])}
    def get(self, sid): return self.rows.get(sid)
    def save_proof(self, *a):
        if self.fail: raise RuntimeError("lakebase down")
        self.saved.append(a)
    def latest_proof(self): return {"title": "Fix price"} if self.saved else None
    def live_page(self, page_id): return {"version": 2, "published_by": "jw", "published_at": "t"}
    def health(self): return {"t0_auto": 0, "t1_approved_no_edit_pct": None, "t2_reviews": 0, "blocked": 0}

FakeReads.before_after = lambda self, ids: {"before": {"answer": "a", "cited": []}, "after": {"answer": "b", "cited": []},
                                            "engine": "Gemini", "prompt_id": "q111", "prompt_text": "Game day food ideas for a crowd"}
FakeReads.cluster_before_after = lambda self, ids: {"share_before": 0.1, "share_after": 0.4, "accuracy_before": 50.0, "accuracy_after": 100.0}
FakeReads.weekly = lambda self: []

def _with_repo(repo, fn):
    app.dependency_overrides[deps.get_suggestions] = lambda: repo
    try:
        return fn()
    finally:
        app.dependency_overrides[deps.get_suggestions] = lambda: S

def test_published_status_saves_proof_and_impact_returns_it():
    repo = ProofSuggestions()
    def run():
        assert c.get("/api/suggestions/p1/status").json()["state"] == "published"
        return c.get("/api/impact").json()
    imp = _with_repo(repo, run)
    assert repo.saved and repo.saved[0][0] == "p1" and imp["proof"] == {"title": "Fix price"}

def test_proof_save_failure_does_not_break_status():  # Review Focus 3
    r = _with_repo(ProofSuggestions(fail=True), lambda: c.get("/api/suggestions/p1/status"))
    assert r.status_code == 200 and r.json()["before"]["answer"] == "a"

def test_evidence_route_adds_live_page():
    ev = _with_repo(ProofSuggestions(), lambda: c.get("/api/opportunities/opp_1/evidence").json())
    assert ev["live_page"]["version"] == 2


class UnproofedSuggestions(ProofSuggestions):
    """A publish finished while nobody polled status (Fix page closed): no proof row yet."""
    def __init__(self, fail_lookup=False):
        super().__init__(); self.fail_lookup = fail_lookup
    def latest_published_needing_proof(self):
        if self.fail_lookup: raise RuntimeError("lakebase down")
        if self.saved: return None
        return {"suggestion_id": "p1", "title": "Fix price", "reviewer": "jw@x.com", "prompt_ids": ["q001"]}

def test_impact_saves_proof_for_unproofed_published_suggestion():
    repo = UnproofedSuggestions()
    imp = _with_repo(repo, lambda: c.get("/api/impact").json())
    assert len(repo.saved) == 1
    sid, title, reviewer, ba, summary = repo.saved[0]
    assert (sid, title, reviewer) == ("p1", "Fix price", "jw@x.com") and ba["after"]["answer"] == "b" and summary["share_after"] == 0.4
    assert imp["proof"] == {"title": "Fix price"}

def test_impact_skips_proof_when_no_before_after():
    repo = UnproofedSuggestions()
    orig = FakeReads.before_after
    FakeReads.before_after = lambda self, ids: None
    try:
        imp = _with_repo(repo, lambda: c.get("/api/impact").json())
    finally:
        FakeReads.before_after = orig
    assert repo.saved == [] and imp["proof"] is None

def test_impact_still_200_when_safety_net_raises():
    r = _with_repo(UnproofedSuggestions(fail_lookup=True), lambda: c.get("/api/impact"))
    assert r.status_code == 200 and r.json()["proof"] is None
    failing_save = UnproofedSuggestions(); failing_save.fail = True
    r = _with_repo(failing_save, lambda: c.get("/api/impact"))
    assert r.status_code == 200 and r.json()["proof"] is None

def test_status_and_safety_net_carry_engine_and_question():  # P2
    repo = ProofSuggestions()
    st = _with_repo(repo, lambda: c.get("/api/suggestions/p1/status").json())
    assert st["engine"] == "Gemini" and st["prompt_text"] == "Game day food ideas for a crowd" and st["prompt_id"] == "q111"
    assert repo.saved[0][3]["engine"] == "Gemini" and repo.saved[0][3]["prompt_text"] == "Game day food ideas for a crowd"
    repo = UnproofedSuggestions()
    _with_repo(repo, lambda: c.get("/api/impact"))
    assert repo.saved[0][3]["engine"] == "Gemini"
