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
    assert "ORDER BY v.version DESC LIMIT 1" in log[-1][0] and log[-1][1] == ("pg_deals",)

def test_latest_published_needing_proof_sql_shape():
    log = []
    repo = SuggestionRepo(lambda: LogConn(log, [("s1", "Fix price", "jw@x.com", ["q001"])], ["suggestion_id", "title", "reviewer", "prompt_ids"]))
    assert repo.latest_published_needing_proof() == {"suggestion_id": "s1", "title": "Fix price", "reviewer": "jw@x.com", "prompt_ids": ["q001"]}
    sql = log[-1][0]
    assert "s.epoch = (SELECT epoch FROM demo_state WHERE id = 1)" in sql and "s.state = 'published'" in sql
    assert "p.saved_at >= s.reviewed_at" in sql
    assert sql.endswith("ORDER BY s.reviewed_at DESC NULLS LAST LIMIT 1")

def test_latest_published_needing_proof_none_when_empty():
    assert SuggestionRepo(lambda: LogConn([])).latest_published_needing_proof() is None


# R1 and S1 run the repo's real SQL against SQLite (same shapes as Lakebase for these queries).
import sqlite3

class SqliteConn:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def commit(self): self.db.commit()
    def execute(self, sql, args=()):
        cur = self.db.execute(sql.replace("%s", "?"), args)
        cur.description and setattr(self, "_d", cur.description)
        return type("C", (), {"description": [type("D", (), {"name": d[0]}) for d in cur.description or []],
                              "fetchall": cur.fetchall, "fetchone": cur.fetchone})()

def _db():
    db = sqlite3.connect(":memory:")
    db.executescript("""
      CREATE TABLE demo_state (id INTEGER, epoch INTEGER); INSERT INTO demo_state VALUES (1, 11);
      CREATE TABLE suggestions (suggestion_id TEXT, epoch INTEGER, title TEXT, reviewer TEXT, prompt_ids TEXT, state TEXT, reviewed_at TEXT);
      CREATE TABLE proof_results (suggestion_id TEXT PRIMARY KEY, saved_at TEXT);
      CREATE TABLE cms_page_versions (page_id TEXT, version INTEGER, published_by TEXT, published_at TEXT);""")
    return db

def test_rehearsed_proof_is_refreshed_by_a_newer_publish():
    db = _db()
    db.execute("INSERT INTO suggestions VALUES ('sg_gd', 11, 'Answer game day party questions', 'jw@x.com', 'q111', 'published', '2026-10-14T15:00:00Z')")
    db.execute("INSERT INTO proof_results VALUES ('sg_gd', '2026-10-14T08:00:00Z')")  # morning rehearsal, then Reset, then live publish
    u = SuggestionRepo(lambda: SqliteConn(db)).latest_published_needing_proof()
    assert u["suggestion_id"] == "sg_gd" and u["title"] == "Answer game day party questions"

def test_fresh_proof_is_not_recomputed():
    db = _db()
    db.execute("INSERT INTO suggestions VALUES ('sg_gd', 11, 't', 'jw@x.com', 'q111', 'published', '2026-10-14T15:00:00Z')")
    db.execute("INSERT INTO proof_results VALUES ('sg_gd', '2026-10-14T15:06:00Z')")
    assert SuggestionRepo(lambda: SqliteConn(db)).latest_published_needing_proof() is None

def test_needing_proof_picks_latest_publish_of_current_epoch():
    db = _db()
    db.executemany("INSERT INTO suggestions VALUES (?, ?, 't', 'r', 'q1', ?, ?)", [
        ("old_epoch", 10, "published", "2026-10-14T16:00:00Z"), ("a", 11, "published", "2026-10-14T14:00:00Z"),
        ("b", 11, "published", "2026-10-14T15:00:00Z"), ("c", 11, "pending_review", "2026-10-14T17:00:00Z")])
    assert SuggestionRepo(lambda: SqliteConn(db)).latest_published_needing_proof()["suggestion_id"] == "b"

def test_live_page_names_the_reviewer_not_the_suggestion_id():  # S1
    db = _db()
    db.execute("INSERT INTO suggestions VALUES ('sg_44289b2d12cd', 11, 't', 'jw@x.com', 'q1', 'published', '2026-10-14T15:00:00Z')")
    db.executemany("INSERT INTO cms_page_versions VALUES (?, ?, ?, ?)", [
        ("pg_deals", 2, "sg_44289b2d12cd", "2026-10-14T15:05:00Z"), ("pg_deals", 1, "seed", "2026-10-01T00:00:00Z"),
        ("pg_menu", 4, "seed", "2026-10-02T00:00:00Z")])
    repo = SuggestionRepo(lambda: SqliteConn(db))
    assert repo.live_page("pg_deals") == {"version": 2, "published_by": "jw@x.com", "published_at": "2026-10-14T15:05:00Z"}
    assert repo.live_page("pg_menu")["published_by"] == "seed"  # no matching suggestion: keep the raw value
    assert repo.live_page("pg_none") is None


# P2: engine and question are saved with the proof; prompt_text is optional until ops adds the column.
class MissingColumnConn(LogConn):
    def execute(self, sql, args=()):
        if "prompt_text" in sql:
            self.log.append(("FAILED " + " ".join(sql.split()), args))
            raise RuntimeError('column "prompt_text" of relation "proof_results" does not exist')
        return super().execute(sql, args)

BA = {"before": {"answer": "old", "cited": ["d1"]}, "after": {"answer": "new", "cited": ["lce_pg_deals"]},
      "engine": "Gemini", "prompt_id": "q111", "prompt_text": "Game day food ideas for a crowd"}

def test_save_proof_stores_engine_and_question():
    log = []
    SuggestionRepo(lambda: LogConn(log)).save_proof("s1", "t", "jw", BA, {})
    sql, args = log[-1]
    assert "engine" in sql and "prompt_text" in sql and "engine = EXCLUDED.engine" in sql and "prompt_text = EXCLUDED.prompt_text" in sql
    assert "Gemini" in args and "Game day food ideas for a crowd" in args

def test_save_proof_retries_without_prompt_text_column():
    log = []
    SuggestionRepo(lambda: MissingColumnConn(log)).save_proof("s1", "t", "jw", BA, {})
    assert log[0][0].startswith("FAILED") and "prompt_text" not in log[-1][0] and "Gemini" in log[-1][1]

def test_save_proof_other_errors_propagate():
    class Down(LogConn):
        def execute(self, sql, args=()): raise RuntimeError("connection refused")
    import pytest
    with pytest.raises(RuntimeError):
        SuggestionRepo(lambda: Down([])).save_proof("s1", "t", "jw", BA, {})

def test_save_proof_defaults_engine_to_claude():
    log = []
    SuggestionRepo(lambda: LogConn(log)).save_proof("s1", "t", "jw", {"before": {"answer": "a"}, "after": {"answer": "b"}}, None)
    assert "Claude" in log[-1][1]

def test_latest_proof_without_prompt_text_column():
    log = []
    cols = ["suggestion_id", "title", "engine"]
    class Conn2(MissingColumnConn):
        def __init__(self, log): super().__init__(log, [("s1", "t", "Claude")], cols)
    p = SuggestionRepo(lambda: Conn2(log)).latest_proof()
    assert p == {"suggestion_id": "s1", "title": "t", "engine": "Claude", "prompt_text": None}
