import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from backend.fixes import FixRepo


class Cur:
    def __init__(self, rows, cols): self._rows, self.description = rows, [type("D", (), {"name": c}) for c in cols]
    def fetchall(self): return self._rows
    def fetchone(self): return self._rows[0] if self._rows else None


class Conn:
    def __init__(self, log, rows=None, cols=None): self.log, self.rows, self.cols = log, rows if rows is not None else [(1,)], cols or ["x"]
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def commit(self): pass
    def execute(self, sql, args=()):
        self.log.append((" ".join(sql.split()), args))
        if "count(DISTINCT object_ref)" in sql:
            return Cur([(1, "EX-03")], ["n", "rule_id"])
        return Cur(self.rows, self.cols)


def repo(log, rows=None, cols=None):
    return FixRepo(lambda: Conn(log, rows, cols))


def test_claim_is_the_atomic_gate():
    log = []
    assert repo(log, [("fx_a",)], ["fix_id"]).claim("fx_a", "jj@x.com")
    q, args = log[-1]
    assert "state = 'publishing'" in q and "WHERE fix_id = %s AND state = 'pending_review'" in q
    assert "epoch = (SELECT epoch FROM demo_state WHERE id = 1)" in q and args == ("jj@x.com", "fx_a")
    assert not repo([], [], ["fix_id"]).claim("fx_a", "x")


def test_claim_t0_only_pending_and_returns_ids():
    log = []
    assert repo(log, [("fx_1",), ("fx_2",)], ["fix_id"]).claim_t0("r") == ["fx_1", "fx_2"]
    q = log[-1][0]
    assert "tier = 'T0' AND state = 'pending_review'" in q and "RETURNING fix_id" in q


def test_release_is_scoped_to_publishing():
    log = []
    repo(log).release("fx_a", "Publish failed. Try again.")
    q, args = log[-1]
    assert "state = 'pending_review'" in q and "AND state = 'publishing'" in q and args == ("Publish failed. Try again.", "fx_a")


def test_list_excludes_blocked():
    log = []
    repo(log, [], ["fix_id"]).list()
    assert "state <> 'blocked'" in log[-1][0] and "ORDER BY issue_rank, tier" in log[-1][0]


def test_quarantine_counts_ingest_posts_only():
    log = []
    q = repo(log, [("ingest", "t1"), ("suggest", "t2"), ("publish", "t3")], ["enforcement_point", "occurred_at"]).quarantine_points()
    assert q["count"] == 1 and q["rule_id"] == "EX-03" and [p["enforcement_point"] for p in q["points"]] == ["ingest", "suggest", "publish"]
    count_sql, points_sql = log[0][0], log[1][0]
    assert "count(DISTINCT object_ref)" in count_sql and "WHERE enforcement_point = 'ingest'" in count_sql
    assert "object_ref IN (SELECT object_ref FROM audit_events WHERE enforcement_point = 'ingest'" in points_sql


def test_edit_only_while_pending_and_stores_the_rechecked_fix():
    log = []
    final = {"sentences": [{"text": "a", "fact_ids": ["F12"]}], "grounding_fact_ids": ["F12"], "checks": [], "tier": "T1",
             "state": "pending_review", "exclusion_rule_id": None}
    out = repo(log, [("fx_a", "T1")], ["fix_id", "tier"]).edit("fx_a", "## x\na", final)
    q, args = log[-1]
    assert out == {"fix_id": "fx_a", "tier": "T1"} and "WHERE fix_id = %s AND state = 'pending_review'" in q
    assert args[0] == "## x\na" and args[2] == ["F12"] and args[-1] == "fx_a"


def test_store_state_writes_only_touch_publishing_rows():
    log = []
    repo(log).set_state("fx_a", "published")
    assert "AND state = 'publishing'" in log[-1][0]
    repo(log).set_step("fx_a", 3)
    assert "AND state = 'publishing'" in log[-1][0] and log[-1][1] == (3, "fx_a")
