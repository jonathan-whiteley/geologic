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
