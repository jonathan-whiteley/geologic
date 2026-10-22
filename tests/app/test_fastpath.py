import sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from main import app
from backend import deps
from backend.fastpath import FastPublisher
from geologic.publish_flow import FRIENDLY_ERROR

NOW = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)

class Repo:
    def __init__(self):
        self.rows = {"fx_a": {"fix_id": "fx_a", "state": "pending_review", "tier": "T1", "issue_id": "is_1", "epoch": 2},
                     "fx_t0": {"fix_id": "fx_t0", "state": "pending_review", "tier": "T0", "issue_id": "is_2", "epoch": 2},
                     "fx_t0b": {"fix_id": "fx_t0b", "state": "publishing", "tier": "T0", "issue_id": "is_3", "epoch": 2}}
        self.released, self.runs, self.prev = [], {}, []
    def epoch(self): return 2
    @staticmethod
    def _failed(r): return any(not c["ok"] and c["key"] in ("grounded", "policy") for c in r.get("checks") or [])
    def claim(self, fid, who):
        r = self.rows.get(fid)
        if r and r["state"] == "pending_review" and not self._failed(r):
            r.update(state="publishing", reviewed_at=NOW - timedelta(seconds=95)); return True
        return False
    def claim_t0(self, who):
        ids = [k for k, r in self.rows.items() if r["tier"] == "T0" and r["state"] == "pending_review" and not self._failed(r)]
        for k in ids: self.rows[k]["state"] = "publishing"
        return ids
    def release(self, fid, err):
        self.released.append((fid, err))
        r = self.rows.get(fid)
        if r and r["state"] == "publishing":
            r["state"] = "pending_review"; return True
        return False
    def release_many(self, ids, err): [self.release(i, err) for i in ids]
    def set_run(self, ids, run_id): self.runs[tuple(ids)] = run_id
    def get(self, fid): return self.rows.get(fid)
    def status(self, fid):
        r = self.rows.get(fid)
        return None if r is None else {"state": r["state"], "publish_step": 4, "error": None, "reviewed_at": r.get("reviewed_at"), "tier": r["tier"],
                                       "publish_run_id": r.get("publish_run_id")}
    def results(self, fid): return self.prev

class Pub:
    def __init__(self): self.started = []
    def start(self, fid): self.started.append(fid)

class Jobs:
    def __init__(self, fail=False): self.fail, self.calls, self.states, self.asked = fail, [], {}, []
    def run_publish(self, ids):
        if self.fail: raise RuntimeError("jobs down")
        self.calls.append(list(ids)); return 77
    def publish_state(self, run_id):
        self.asked.append(run_id)
        st = self.states.get(run_id)
        return None if st is None else {"run_id": run_id, "life_cycle_state": st, "result_state": None}

c = TestClient(app)

@pytest.fixture
def fakes():
    """Fresh fakes per test. Overrides are set here and the previous ones restored on teardown, never at module level,
    so this module and tests/app/test_routes.py cannot clobber each other's get_jobs at collection time."""
    R, P, J = Repo(), Pub(), Jobs()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.update({deps.get_fix_repo: lambda: R, deps.get_publisher: lambda: P, deps.get_jobs: lambda: J,
                                     deps.get_clock: lambda: (lambda: NOW)})
    yield R, P, J
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)

def test_approve_twice_starts_one_thread(fakes):  # Review Focus 3
    R, P, J = fakes
    assert c.post("/api/fixes/fx_a/approve").status_code == 202
    assert c.post("/api/fixes/fx_a/approve").status_code == 409
    assert P.started == ["fx_a"]

def test_approve_t0_claims_only_pending(fakes):  # Review Focus 3
    R, P, J = fakes
    r = c.post("/api/fixes/approve-t0")
    assert r.status_code == 202 and r.json() == {"run_id": 77, "fix_ids": ["fx_t0"]} and J.calls == [["fx_t0"]]
    assert c.post("/api/fixes/approve-t0").status_code == 409

def test_approve_t0_job_failure_releases_claims(fakes):
    R, P, J = fakes
    app.dependency_overrides[deps.get_jobs] = lambda: Jobs(fail=True)   # the fixture restores the overrides afterwards
    assert c.post("/api/fixes/approve-t0").status_code == 502 and ("fx_t0", "Publish failed. Try again.") in R.released

def test_status_fallback_only_with_rehearsal(fakes):  # Review Focus 2
    R, P, J = fakes
    R.rows["fx_a"].update(state="publishing", reviewed_at=NOW - timedelta(seconds=95))
    R.prev = []
    s = c.get("/api/fixes/fx_a/status").json()
    assert s["state"] == "publishing" and s["fallback"] is None and s["elapsed_s"] == 95 and len(s["step_labels"]) == 5
    R.prev = [{"fix_id": "fx_a", "prompt_id": "q201", "engine": "Claude", "epoch": 1, "issue_id": "is_1", "title": "t", "tier": "T1",
               "asset_type": "owned_patch", "reviewer": "r", "approved_at": NOW - timedelta(hours=5), "measured_at": NOW - timedelta(hours=5),
               "elapsed_s": 41.0, "prompt_text": "p", "status": "ok", "before_mentioned": False, "after_mentioned": True,
               "before_owned_cited": False, "after_owned_cited": True, "before_owned_retrieved": False, "after_owned_retrieved": True,
               "before_position": None, "after_position": 1, "before_claim_tags": ["Outdated"], "after_claim_tags": ["Correct"],
               "before_answer": "b", "after_answer": "a", "before_cited": [], "after_cited": ["lce_pg_deals_game_day"]}]
    s = c.get("/api/fixes/fx_a/status").json()
    assert s["fallback"]["entry"]["rehearsal"] is True and s["fallback"]["rehearsed_at"].startswith("2026-10-22T08:00")
    R.rows["fx_a"]["reviewed_at"] = NOW - timedelta(seconds=30)
    assert c.get("/api/fixes/fx_a/status").json()["fallback"] is None          # under 90 s: no fallback yet

def test_published_status_carries_only_this_runs_entry(fakes):
    R, P, J = fakes
    R.rows["fx_a"].update(state="published", reviewed_at=NOW - timedelta(seconds=40))
    old = {"fix_id": "fx_a", "prompt_id": "q201", "engine": "Claude", "epoch": 1, "title": "t", "tier": "T1", "asset_type": "owned_patch",
           "measured_at": NOW - timedelta(hours=5), "status": "ok", "before_mentioned": False, "after_mentioned": False,
           "before_owned_cited": False, "after_owned_cited": False, "before_claim_tags": [], "after_claim_tags": [],
           "before_answer": "b", "after_answer": "a", "before_cited": [], "after_cited": []}
    old["approved_at"] = NOW - timedelta(hours=5)
    # This run's rows carry approved_at == reviewed_at. Its measured_at (app clock) is a little earlier than reviewed_at
    # (Postgres now()): clock skew must not drop them.
    R.prev = [old, {**old, "epoch": 2, "approved_at": R.rows["fx_a"]["reviewed_at"], "measured_at": NOW - timedelta(seconds=41),
                    "after_mentioned": True}]
    e = c.get("/api/fixes/fx_a/status").json()["entry"]
    assert e["rehearsal"] is False and e["prompts"][0]["after"]["mentioned"] == 1
    R.rows["fx_a"]["state"] = "publishing"
    R.rows["fx_a"]["reviewed_at"] = NOW - timedelta(seconds=95)
    R.prev[1]["approved_at"] = R.rows["fx_a"]["reviewed_at"]
    fb = c.get("/api/fixes/fx_a/status").json()["fallback"]
    assert fb["entry"]["epoch"] == 1 and fb["rehearsed_at"].startswith("2026-10-22T08:00")   # only the rehearsal stands in

def test_fast_publish_exception_releases():  # Review Focus 1
    class BoomRepo(Repo):
        def get(self, fid): raise RuntimeError("lakebase blip")
    repo = BoomRepo()
    pub = FastPublisher(repo, store_factory=lambda: None, rules_fn=lambda: [], focus_fn=lambda i: None, clock=lambda: NOW,
                        spawn=lambda f: f())
    pub.start("fx_a")
    assert repo.released == [("fx_a", FRIENDLY_ERROR)]

def test_edit_regrounds_unchanged_and_edited_sentences():  # spec 5.4: edits stay grounded
    from datetime import date
    from backend.fixes_edit import edit_fix
    from geologic.datagen.reference import brand_facts, exclusion_rules, menu_items
    fix = {"fix_id": "fx_a", "asset_type": "owned_patch", "section_id": "game-day-deals", "op": "insert", "persona_id": None,
           "rationale": "r", "grounding_fact_ids": ["F12", "F14"],
           "sentences": [{"text": "The Game Day Party Pack feeds 12 for $29.99.", "fact_ids": ["F12", "F14"]}]}
    text = "## Feeding 12\nThe Game Day Party Pack feeds 12 for $29.99. The Game Day Party Pack is $29.99 today. Grab one."
    final = edit_fix(fix, text, facts=brand_facts(), rules=exclusion_rules(), today=date(2026, 10, 21),
                     item_names=[m["name"] for m in menu_items()], persona_names=["Jared Goff"], judge=lambda t, g: [])
    sents = [x for x in final["sentences"] if x["kind"] != "heading"]   # Task 6 fix round: verify() also returns headings
    assert [x["fact_ids"] for x in sents] == [["F12", "F14"], ["F12"], []]
    assert [x["kind"] for x in sents] == ["fact", "fact", "copy"]
    assert final["tier"] == "T1" and all(c["ok"] for c in final["checks"])


def test_approve_releases_when_the_publisher_cannot_start(fakes):   # fix round 1
    R, P, J = fakes
    class Dead:
        def start(self, fid): raise RuntimeError("cannot start thread")
    app.dependency_overrides[deps.get_publisher] = lambda: Dead()
    r = c.post("/api/fixes/fx_a/approve")
    assert r.status_code == 502 and R.released == [("fx_a", FRIENDLY_ERROR)] and R.rows["fx_a"]["state"] == "pending_review"


def test_status_releases_a_stuck_publishing_row(fakes):   # fix round 1: a dead thread never leaves a row publishing
    R, P, J = fakes
    R.rows["fx_a"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=6))
    s = c.get("/api/fixes/fx_a/status").json()
    assert R.released == [("fx_a", FRIENDLY_ERROR)] and s["state"] == "pending_review" and s["error"] == FRIENDLY_ERROR
    assert s["fallback"] is None
    R.released.clear()
    R.rows["fx_a"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=4))
    assert c.get("/api/fixes/fx_a/status").json()["state"] == "publishing" and R.released == []


def test_status_keeps_a_job_run_row_publishing_until_the_run_ends(fakes):   # final review I1
    R, P, J = fakes
    R.rows["fx_t0"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=6), publish_run_id=77)
    for live in ("PENDING", "QUEUED", "RUNNING", "TERMINATING"):
        J.states[77] = live
        assert c.get("/api/fixes/fx_t0/status").json()["state"] == "publishing" and R.released == []
    J.states.pop(77)   # unreadable run: never guess, keep the row
    assert c.get("/api/fixes/fx_t0/status").json()["state"] == "publishing" and R.released == []
    J.states[77] = "TERMINATED"
    s = c.get("/api/fixes/fx_t0/status").json()
    assert R.released == [("fx_t0", FRIENDLY_ERROR)] and s["state"] == "pending_review" and s["error"] == FRIENDLY_ERROR


def test_status_asks_the_job_only_for_job_rows_past_the_stuck_window(fakes):   # final review I1
    R, P, J = fakes
    R.rows["fx_t0"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=2), publish_run_id=77)
    J.states[77] = "TERMINATED"
    assert c.get("/api/fixes/fx_t0/status").json()["state"] == "publishing" and J.asked == [] and R.released == []
    R.rows["fx_a"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=6))   # fast path row: no run id
    assert c.get("/api/fixes/fx_a/status").json()["state"] == "pending_review" and J.asked == []


def test_status_rereads_when_the_row_left_publishing_before_the_release(fakes):   # final review I1
    R, P, J = fakes
    class Racy(Repo):
        def status(self, fid):
            s = super().status(fid)
            if s and s["state"] == "publishing":
                self.rows[fid]["state"] = "published"   # the publisher finished between the read and the release
            return s
    racy = Racy()
    racy.rows["fx_a"].update(state="publishing", reviewed_at=NOW - timedelta(minutes=6))
    app.dependency_overrides[deps.get_fix_repo] = lambda: racy
    s = c.get("/api/fixes/fx_a/status").json()
    assert racy.released == [("fx_a", FRIENDLY_ERROR)] and s["state"] == "published" and s["error"] is None


def test_approve_refuses_a_fix_with_a_failed_blocking_check(fakes):   # final review I2
    R, P, J = fakes
    R.rows["fx_a"]["checks"] = [{"key": "grounded", "ok": False, "label": "x"}, {"key": "style", "ok": False, "label": "y"}]
    r = c.post("/api/fixes/fx_a/approve")
    assert r.status_code == 409 and r.json()["detail"] == "Fix the failed checks to approve" and P.started == []
    R.rows["fx_a"]["checks"] = [{"key": "grounded", "ok": True, "label": "x"}]
    assert c.post("/api/fixes/fx_a/approve").status_code == 202 and P.started == ["fx_a"]
    r = c.post("/api/fixes/fx_a/approve")   # already publishing: the old message
    assert r.status_code == 409 and r.json()["detail"] == "This fix is already publishing or no longer needs review."


def test_approve_t0_skips_fixes_with_failed_blocking_checks(fakes):   # final review I2
    R, P, J = fakes
    R.rows["fx_t0"]["checks"] = [{"key": "policy", "ok": False, "label": "Blocked by EX-03"}]
    assert c.post("/api/fixes/approve-t0").status_code == 409 and J.calls == []
    R.rows["fx_t0c"] = {"fix_id": "fx_t0c", "state": "pending_review", "tier": "T0", "issue_id": "is_4", "epoch": 2, "checks": []}
    r = c.post("/api/fixes/approve-t0")
    assert r.status_code == 202 and r.json()["fix_ids"] == ["fx_t0c"] and R.rows["fx_t0"]["state"] == "pending_review"
