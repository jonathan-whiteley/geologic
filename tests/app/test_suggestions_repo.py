import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from backend.suggestions import SuggestionRepo


class Cur:
    def __init__(self, rows, cols): self._rows, self.description = rows, [type("D", (), {"name": c}) for c in cols]
    def fetchall(self): return self._rows
    def fetchone(self): return self._rows[0] if self._rows else None


class Conn:
    def __init__(self, log): self.log = log
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def commit(self): pass
    def execute(self, sql, args=()):
        self.log.append((" ".join(sql.split()), args))
        if "audit_events" in sql:
            return Cur([(2,)], ["n"])
        if "t0_auto" in sql:
            return Cur([(3, 0, 1, 1)], ["t0_auto", "t2_reviews", "t1_published", "t1_reviewed"])
        return Cur([(1,)], ["x"])


def test_health_counts_distinct_blocked_objects():  # finding 16: reruns re-audit the same red-team row
    log = []
    h = SuggestionRepo(lambda: Conn(log)).health()
    assert h["blocked"] == 2 and h["t1_approved_no_edit_pct"] == 100
    assert any("count(DISTINCT object_ref)" in q for q, _ in log)


def test_release_is_scoped_to_publishing():  # finding 2
    log = []
    assert SuggestionRepo(lambda: Conn(log)).release("s1", "Publish failed. Try again.")
    q, args = log[-1]
    assert "state = 'pending_review'" in q and "AND state = 'publishing'" in q and args == ("Publish failed. Try again.", "s1")


class LogConn(Conn):
    def __init__(self, log, rows=None, cols=None):
        super().__init__(log); self.rows, self.cols = rows or [], cols or []
    def execute(self, sql, args=()):
        self.log.append((" ".join(sql.split()), args))
        if sql.lstrip().upper().startswith("SELECT"):
            return Cur(self.rows, self.cols)
        return Cur([(1,)], ["x"])

def test_save_proof_upserts():
    log = []
    ba = {"before": {"answer": "old", "cited": ["d1"]}, "after": {"answer": "new", "cited": ["lce_pg_deals"]}}
    SuggestionRepo(lambda: LogConn(log)).save_proof("s1", "Fix price", "jw@x.com", ba,
                                                   {"share_before": 0.1, "share_after": 0.4, "accuracy_before": 50.0, "accuracy_after": 100.0})
    sql, args = log[-1]
    assert sql.startswith("INSERT INTO proof_results") and "ON CONFLICT (suggestion_id) DO UPDATE" in sql
    assert args[0] == "s1" and "old" in args and "new" in args and 0.4 in args

def test_latest_proof_none_when_empty():
    assert SuggestionRepo(lambda: LogConn([])).latest_proof() is None

def test_live_page_latest_version():
    log = []
    repo = SuggestionRepo(lambda: LogConn(log, [(3, "jw@x.com", "2026-10-13T10:00:00Z")], ["version", "published_by", "published_at"]))
    assert repo.live_page("pg_deals") == {"version": 3, "published_by": "jw@x.com", "published_at": "2026-10-13T10:00:00Z"}
    assert "ORDER BY version DESC LIMIT 1" in log[-1][0] and log[-1][1] == ("pg_deals",)

def test_latest_published_without_proof_sql_shape():
    log = []
    repo = SuggestionRepo(lambda: LogConn(log, [("s1", "Fix price", "jw@x.com", ["q001"])], ["suggestion_id", "title", "reviewer", "prompt_ids"]))
    assert repo.latest_published_without_proof() == {"suggestion_id": "s1", "title": "Fix price", "reviewer": "jw@x.com", "prompt_ids": ["q001"]}
    sql = log[-1][0]
    assert "s.epoch = (SELECT epoch FROM demo_state WHERE id = 1)" in sql and "s.state = 'published'" in sql
    assert "NOT EXISTS (SELECT 1 FROM proof_results p WHERE p.suggestion_id = s.suggestion_id)" in sql
    assert sql.endswith("ORDER BY s.reviewed_at DESC NULLS LAST LIMIT 1")

def test_latest_published_without_proof_none_when_empty():
    assert SuggestionRepo(lambda: LogConn([])).latest_published_without_proof() is None
