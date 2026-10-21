import sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend import reads as R
from geologic.results import results_rows

NOW = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)   # a Thursday; its Monday is 2026-10-19


def fake_query(script):
    calls = []
    def q(sql, params=None):
        calls.append((sql, params))
        for needle, rows in script:
            if needle in sql:
                return [dict(r) for r in rows]
        return []
    return q, calls


def ans(engine, mentioned, cited, status="ok"):
    return {"engine": engine, "status": status, "lce_mentioned": mentioned, "lce_rank": 1 if mentioned else None,
            "cited_doc_ids": cited, "retrieved_doc_ids": cited, "answer": "x"}


def fix_rows(fix_id, epoch, at):
    fix = {"fix_id": fix_id, "epoch": epoch, "issue_id": "is_1", "title": f"Patch our page: {fix_id}", "tier": "T1",
           "asset_type": "owned_patch", "reviewer": "r", "prompt_ids": ["q201"]}
    before = {("q201", "Claude"): {"answer": ans("Claude", False, []), "claims": []}}
    after = {("q201", "Claude"): {"answer": ans("Claude", True, ["lce_pg_deals_game_day"]), "claims": []}}
    return results_rows(fix, before, after, now=at, approved_at=at)


class Repo:
    def __init__(self, boom=False): self.boom = boom
    def epoch(self): return 2
    def all_results(self):
        if self.boom: raise RuntimeError('relation "fix_results" does not exist')
        return fix_rows("fx_old", 1, NOW - timedelta(hours=5)) + fix_rows("fx_new", 2, NOW)
    def list(self):
        return [{"fix_id": "fx_new", "issue_id": "is_1", "page_id": "pg_deals_game_day", "state": "published", "reviewed_at": NOW},
                {"fix_id": "fx_old", "issue_id": "is_2", "page_id": "pg_item_classic_pepperoni", "state": "pending_review", "reviewed_at": None},
                {"fix_id": "fx_m", "issue_id": "is_m2", "page_id": "pg_moment_x", "state": "published", "reviewed_at": NOW - timedelta(days=1)}]


SCRIPT = [
    ("v_phase_metrics", [{"phase": "before", "answers": 120, "mention_lce": 80, "cite_lce": 40, "pick_lce_first": 30, "owned_retrieved": 50,
                          "answer_share": 0.587, "mention_rate": 0.706, "avg_rank": 1.9},
                         {"phase": "after", "answers": 120, "mention_lce": 84, "cite_lce": 46, "pick_lce_first": 33, "owned_retrieved": 58,
                          "answer_share": 0.61, "mention_rate": 0.73, "avg_rank": 1.8}]),
    ("v_phase_claims", [{"phase": "before", "wrong_or_outdated": 19, "correct": 80}, {"phase": "after", "wrong_or_outdated": 15, "correct": 84}]),
    ("v_answer_share_weekly", [{"week_start": "2026-10-19", "brand": "Little Caesars", "answer_share": 0.6}]),
    ("v_movers", [{"prompt_id": "q201", "prompt_text": "a", "cluster": "game_day_party", "naming_before": 1, "naming_after": 3,
                   "owned_cited_before": 0, "owned_cited_after": 1},
                  {"prompt_id": "q002", "prompt_text": "b", "cluster": "value", "naming_before": 2, "naming_after": 2,
                   "owned_cited_before": 1, "owned_cited_after": 1},
                  {"prompt_id": "q115", "prompt_text": "c", "cluster": "comparison", "naming_before": 2, "naming_after": 1,
                   "owned_cited_before": 0, "owned_cited_after": 0}]),
    ("v_prompt_status", [{"prompt_id": "q201", "cluster": "game_day_party", "engines_answered": 4, "engines_naming": 1},
                         {"prompt_id": "q202", "cluster": "game_day_party", "engines_answered": 4, "engines_naming": 2},
                         {"prompt_id": "q002", "cluster": "value", "engines_answered": 3, "engines_naming": 3}]),
    ("moment_id IS NOT NULL", [{"issue_id": "is_m1", "moment_id": "m_goff"}, {"issue_id": "is_m2", "moment_id": "m_done"}]),
    ("moments", [{"moment_id": "m_done", "title": "Captured", "prompt_ids": ["q202"]},
                 {"moment_id": "m_goff", "title": "Goff", "prompt_ids": ["q202"]},
                 {"moment_id": "m_puffs", "title": "Puffs", "prompt_ids": ["s_abc123"]}]),
    ("site_pages", [{"page_id": "pg_deals_game_day", "url": "https://littlecaesars.com/deals/game-day"}]),
]


def test_impact_assembles_every_block(monkeypatch):
    monkeypatch.setattr(R, "query", fake_query(SCRIPT)[0])
    out = R.Reads().impact(Repo())
    assert (out["funnel"]["before"]["cite_lce"], out["funnel"]["after"]["cite_lce"]) == (40, 46)
    assert out["leading"]["after"] == {"owned_retrieved": 58, "cite_lce": 46, "wrong_or_outdated": 15}
    assert out["movers"]["gains"][0]["delta"] == 3 and out["movers"]["drops"][0]["delta"] == -1
    assert [m["prompt_id"] for m in out["movers"]["gains"] + out["movers"]["drops"]] == ["q201", "q115"]   # zero deltas excluded
    assert out["missed_by_cluster"] == [{"cluster": "game_day_party", "missed": 5}]
    assert [e["fix_id"] for e in out["ledger"]] == ["fx_new", "fx_old"] and out["ledger"][1]["rehearsal"] is True
    assert {m["fix_id"]: m["week_start"] for m in out["markers"]} == {"fx_new": "2026-10-19", "fx_old": "2026-10-19"}
    assert out["weekly"][0]["brand"] == "Little Caesars"


def test_impact_rates_are_fractions(monkeypatch):   # controller pin: no percent scaling anywhere in Impact
    monkeypatch.setattr(R, "query", fake_query(SCRIPT)[0])
    lag = R.Reads().impact(Repo())["lagging"]
    assert lag["before"] == {"answer_share": 0.587, "mention_rate": 0.706, "avg_rank": 1.9} and lag["after"]["mention_rate"] == 0.73


def test_patched_pages_most_recently_approved_first(monkeypatch):   # controller pin: the UI defaults to patched_pages[0]
    monkeypatch.setattr(R, "query", fake_query(SCRIPT)[0])
    pages = R.Reads().impact(Repo())["patched_pages"]
    # deals: published now; classic pepperoni: a rehearsal ledger entry 5 h ago; moment page: published a day ago.
    # A page missing from site_pages (a new page after Reset) gets the NEW_PAGE_URL path.
    assert pages == [{"doc_id": "lce_pg_deals_game_day", "label": "/deals/game-day"},
                     {"doc_id": "lce_pg_item_classic_pepperoni", "label": "/answers/item-classic-pepperoni"},
                     {"doc_id": "lce_pg_moment_x", "label": "/answers/moment-x"}]


def test_live_moments_flag_untracked_and_captured(monkeypatch):
    monkeypatch.setattr(R, "query", fake_query(SCRIPT)[0])
    live = {m["moment_id"]: m for m in R.Reads().impact(Repo())["live_moments"]}
    assert "m_done" not in live                       # its issue has a published fix this epoch
    assert live["m_goff"]["tracked"] is True and live["m_goff"]["issue_id"] == "is_m1"
    assert live["m_puffs"]["tracked"] is False and live["m_puffs"]["issue_id"] is None


def test_impact_survives_missing_results_table(monkeypatch):
    monkeypatch.setattr(R, "query", fake_query(SCRIPT)[0])
    out = R.Reads().impact(Repo(boom=True))
    assert out["ledger"] == [] and out["markers"] == [] and out["funnel"]["after"]["answers"] == 120


def test_citations_rejects_unsafe_doc_id(monkeypatch):
    q, calls = fake_query([("v_doc_citations", [{"started_at": "t", "citations": 3, "prompts": 2, "prompt_ids": ["q201"]}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().doc_citations("lce_pg_x'; --") is None and calls == []
    assert R.Reads().doc_citations("lce_pg_deals_game_day")[0]["citations"] == 3 and calls[0][1] == {"d": "lce_pg_deals_game_day"}


@pytest.fixture
def client():
    from main import app
    from backend import deps
    class Reads:
        def impact(self, repo): return {"ledger": [], "repo": type(repo).__name__}
        def doc_citations(self, d): return None if "'" in d else [{"citations": 1}]
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.update({deps.get_reads: lambda: Reads(), deps.get_fix_repo: lambda: Repo()})
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def test_impact_route_200(client):
    r = client.get("/api/impact")
    assert r.status_code == 200 and r.json() == {"ledger": [], "repo": "Repo"}
    assert client.get("/api/impact/citations?doc_id=lce_pg_menu").json() == [{"citations": 1}]
    assert client.get("/api/impact/citations?doc_id=x'").status_code == 400
