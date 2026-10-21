import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from datetime import date
from fastapi.testclient import TestClient
from backend import reads as R
from geologic.datagen.reference import brand_facts

ROUNDUP = "editorial_superbowl_roundup_2024"
KEY = f"Outdated|{ROUNDUP}|party_pack|price"
TODAY = date(2026, 10, 21)
BODY = "Feeding 12 for the big game? Little Caesars' Game Day Party Pack is $24.99 and feeds about 12. Pizza Hut has wings."


def fake_query(script):
    calls = []
    def q(sql, params=None):
        calls.append((sql, params))
        for needle, rows in script:
            if needle in sql:
                return [dict(r) for r in rows]
        return []
    return q, calls


def issue(**k):
    return {"issue_id": "is_0123456789", "rank": 1, "issue_type": "outdated", "title": "t", "cluster": "game_day_party",
            "action_lane": "request_correction", "prompt_ids": ["q201", "x;drop"], "missed_answers": 3, "moment_id": None,
            "source_doc_id": ROUNDUP, "subject": "party_pack", "attribute": "price", "stated_value": "$24.99", "claim_keys": [KEY], **k}


def script(i, extra=()):
    return [("FROM jdub_demo.geologic.issues", [i]), *extra,
            ("FROM jdub_demo.geologic.prompts", [{"prompt_id": "q201", "prompt_text": "Super Bowl for 12"}]),
            ("v_latest_claims WHERE prompt_id IN", [{"engine": "Gemini", "prompt_id": "q201", "text": "Party Pack is $24.99.", "stated_value": "$24.99",
                                  "tag": "Outdated", "source_doc_id": ROUNDUP, "subject": "party_pack", "attribute": "price"},
                                 {"engine": "Claude", "prompt_id": "q201", "text": "Crazy Bread is $1.", "stated_value": "$1",
                                  "tag": "Wrong", "source_doc_id": None, "subject": "crazy_bread", "attribute": "price"}]),
            ("web_corpus", [{"doc_id": ROUNDUP, "domain": "partyplanner-weekly.com", "owner_class": "Editorial", "last_updated": None,
                             "title": "Roundup", "url": "https://p", "body": BODY}]),
            ("brand_facts", brand_facts())]


def test_issue_detail_claims_follow_claim_keys(monkeypatch):
    q, calls = fake_query(script(issue()))
    monkeypatch.setattr(R, "query", q)
    d = R.Reads().issue_detail("is_0123456789", today=TODAY)
    assert [(c["engine"], c["tag"], c["prompt_text"]) for c in d["said"]["claims"]] == [("Gemini", "Outdated", "Super Bowl for 12")]
    claim_sql = [s for s, _ in calls if "v_latest_claims" in s]
    assert len(claim_sql) == 1 and "'q201'" in claim_sql[0] and "drop" not in claim_sql[0]


def test_passage_excerpt_is_the_sentence_with_the_value():
    assert R.excerpt(BODY, "$24.99") == "Little Caesars' Game Day Party Pack is $24.99 and feeds about 12."
    assert R.excerpt("x" * 500, None) == "x" * 300


def test_truth_marks_superseded_and_names_the_uc_table(monkeypatch):
    monkeypatch.setenv("CATALOG_NAME", "jdub_demo")
    monkeypatch.setenv("SCHEMA_NAME", "geologic_v3")
    q, _ = fake_query([(n.replace("jdub_demo.geologic.", "jdub_demo.geologic_v3."), r) for n, r in script(issue())])
    monkeypatch.setattr(R, "query", q)
    t = R.Reads().issue_detail("is_0123456789", today=TODAY)["truth"]
    assert [(f["fact_id"], f["current"]) for f in t["facts"]] == [("F12", True), ("F13", False)]
    assert t["uc_table"] == "jdub_demo.geologic_v3.brand_facts"


def test_moment_detail_uses_public_signals_only(monkeypatch):
    m = {"moment_id": "m_goff", "title": "Goff posts Detroit-style", "kind": "persona", "signal_ids": ["sig_goff"], "persona_id": "p_goff",
         "item_id": "detroit_pepperoni", "reach": 1600000, "velocity": 3.2, "image_match": 0.91}
    i = issue(issue_type="moment_gap", moment_id="m_goff", source_doc_id=None, subject=None, attribute=None, stated_value=None,
              claim_keys=[], prompt_ids=["q202"], item_id="detroit_pepperoni")
    extra = [("moments", [m]), ("v_public_signals", [{"signal_id": "sig_goff", "author": "Jared Goff",
                                                      "image_uri": "/Volumes/jdub_demo/geologic_v3/assets/signals/goff_slices_n_stix.jpg",
                                                      "image_match_score": 0.9}]),
             ("personas", [{"display_name": "Jared Goff"}]), ("menu_items", [{"name": "Deep!Deep! Dish Pepperoni"}])]
    q, calls = fake_query(script(i, extra))
    monkeypatch.setattr(R, "query", q)
    d = R.Reads().issue_detail("is_0123456789", today=TODAY)
    mo = d["said"]["moment"]
    assert mo["image_url"] == "/api/signals/sig_goff/image" and mo["image_credit"] == "Photo: Courtesy of Little Caesars"
    assert mo["author"] == "Jared Goff" and mo["item_name"] == "Deep!Deep! Dish Pepperoni" and mo["image_match"] == 0.91
    assert not any("silver_signals" in s for s, _ in calls) and d["said"]["memory"] is False
    assert [s["prompt_id"] for s in d["said"]["scorecards"]] == ["q202"]
    assert "F08" in {f["fact_id"] for f in d["truth"]["facts"]}
    no_signal = [("moments", [m]), ("personas", [{"display_name": "Jared Goff"}]), ("menu_items", [{"name": "Deep!Deep! Dish Pepperoni"}])]
    monkeypatch.setattr(R, "query", fake_query(script(i, no_signal))[0])
    assert R.Reads().issue_detail("is_0123456789", today=TODAY)["said"]["moment"]["author"] is None


def test_memory_issue_has_no_passage(monkeypatch):
    q, _ = fake_query(script(issue(source_doc_id=None, issue_type="wrong")))
    monkeypatch.setattr(R, "query", q)
    said = R.Reads().issue_detail("is_0123456789", today=TODAY)["said"]
    assert said["passage"] is None and said["memory"] is True


def test_unknown_or_unsafe_issue_id_is_none(monkeypatch):
    q, calls = fake_query([])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().issue_detail("is_0123456789") is None and len(calls) == 1
    assert R.Reads().issue_detail("is_x'; --") is None and R.Reads().issue_detail("q201") is None and len(calls) == 1


def test_issue_filters_are_parameters(monkeypatch):
    q, calls = fake_query([("issues", [{"issue_id": "is_0123456789"}])])
    monkeypatch.setattr(R, "query", q)
    R.Reads().issues("outdated", "game_day_party")
    sql, params = calls[0]
    assert "issue_type = :t AND cluster = :c" in sql and params == {"t": "outdated", "c": "game_day_party"} and "ORDER BY rank" in sql


def test_issue_routes_merge_fixes():
    from main import app
    from backend import deps
    class Reads:
        def issues(self, t, c): return [{"issue_id": "is_a"}, {"issue_id": "is_b"}]
        def issue_detail(self, iid): return None if iid == "is_x" else {"issue": {"issue_id": iid}, "said": {}, "truth": {}}
    class Repo:
        def list(self): return [{"fix_id": "fx_2", "issue_id": "is_a", "tier": "T2", "asset_type": "correction_email", "state": "pending_review"},
                                {"fix_id": "fx_1", "issue_id": "is_a", "tier": "T1", "asset_type": "owned_patch", "state": "pending_review",
                                 "patch_text": "p"}]
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.update({deps.get_reads: lambda: Reads(), deps.get_fix_repo: lambda: Repo()})
    try:
        c = TestClient(app)
        rows = c.get("/api/issues?type=outdated").json()
        assert rows[0]["fixes"][0] == {"fix_id": "fx_2", "tier": "T2", "asset_type": "correction_email", "state": "pending_review"}
        assert rows[1]["fixes"] == []
        d = c.get("/api/issues/is_a").json()
        assert [f["fix_id"] for f in d["fixes"]] == ["fx_1", "fx_2"] and d["fixes"][0]["patch_text"] == "p"
        assert [f["tier"] for f in d["issue"]["fixes"]] == ["T1", "T2"]
        r = c.get("/api/issues/is_x")
        assert r.status_code == 404 and r.json()["detail"] == "Unknown issue"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
