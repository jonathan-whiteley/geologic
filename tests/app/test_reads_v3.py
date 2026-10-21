import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from backend import reads as R


def fake_query(script):
    """script: list of (substring, rows) matched in order of appearance in the SQL; records calls."""
    calls = []
    def q(sql, params=None):
        calls.append((sql, params))
        for needle, rows in script:
            if needle in sql:
                if isinstance(rows, Exception):
                    raise rows
                return [dict(r) for r in rows]
        return []
    return q, calls


def test_summary_scales_rates_and_limits_domains(monkeypatch):
    q, calls = fake_query([
        ("v_kpis", [{"answer_share": 0.59, "mention_rate": 0.6, "owned_citation_share": 0.21, "fact_accuracy": 0.9, "wrong_claims": 3,
                     "outdated_claims": 2, "avg_rank": 1.8, "answers": 120, "engines": 4, "tracked_prompts": 30, "last_run_at": None}]),
        ("v_leaderboard", [{"brand": "Little Caesars", "answer_share": 0.59, "avg_position": 1.4, "citation_share": 0.3}]),
        ("v_source_types", [{"owner_class": "Owned", "citations": 30, "share": 0.25}, {"owner_class": "Editorial", "citations": 90, "share": 0.75}]),
        ("v_top_domains", [{"domain": "partyplanner-weekly.com", "owner_class": "Editorial", "citations": 9, "prompts": 3}]),
        ("GROUP BY engine", [{"engine": "Claude", "answers": 30}]),
    ])
    monkeypatch.setattr(R, "query", q)
    s = R.Reads().model_summary()
    k = s["kpis"]
    assert (k["mention_rate"], k["owned_citation_share"], k["fact_accuracy"]) == (60, 21, 90) and k["answer_share"] == 0.59
    assert [x["share"] for x in s["source_types"]] == [25, 75]
    assert s["brands"][0]["logo"] and s["brands"][0]["citation_share"] == 30 and s["gateway"]["answers"] == 30
    dom = next(sql for sql, _ in calls if "v_top_domains" in sql)
    assert "owner_class <> 'Owned'" in dom and "ORDER BY citations DESC" in dom and "LIMIT 5" in dom


def test_prompt_rows_order_by_priority_then_searches(monkeypatch):
    q, calls = fake_query([("v_prompt_status", [{"prompt_id": "q201"}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().prompt_rows() == [{"prompt_id": "q201"}]
    sql = calls[0][0]
    assert "CASE priority WHEN 'Gold' THEN 0 WHEN 'Silver' THEN 1 ELSE 2 END" in sql and "est_monthly_searches DESC" in sql


ROUNDUP = "editorial_superbowl_roundup_2024"


def test_prompt_detail_attaches_docs_and_issue_ids(monkeypatch):
    q, calls = fake_query([
        ("v_prompt_status", [{"prompt_id": "q201", "prompt_text": "Super Bowl for 12", "priority": "Gold"}]),
        ("v_latest_responses", [{"answer_id": "a2", "engine": "Gemini", "status": "ok", "answer": "x", "lce_mentioned": False,
                                 "lce_rank": None, "cited_doc_ids": [], "retrieved_doc_ids": []},
                                {"answer_id": "a1", "engine": "Claude", "status": "ok", "answer": "y", "lce_mentioned": True, "lce_rank": 2,
                                 "cited_doc_ids": [ROUNDUP, "lce_pg_menu"], "retrieved_doc_ids": ["lce_pg_menu", ROUNDUP]}]),
        ("v_latest_claims", [{"answer_id": "a1", "claim_id": "c1", "text": "The Party Pack is $24.99.", "subject": "party_pack",
                              "attribute": "price", "stated_value": "$24.99", "tag": "Outdated", "fact_id": "F13", "source_doc_id": ROUNDUP}]),
        ("web_corpus", [{"doc_id": ROUNDUP, "domain": "partyplanner-weekly.com", "owner_class": "Editorial", "title": "t", "url": "u",
                         "last_updated": None},
                        {"doc_id": "lce_pg_menu", "domain": "littlecaesars.com", "owner_class": "Owned", "title": "m", "url": "v",
                         "last_updated": None}]),
        ("issues", [{"issue_id": "is_0123456789", "claim_keys": [f"Outdated|{ROUNDUP}|party_pack|price"]}]),
    ])
    monkeypatch.setattr(R, "query", q)
    d = R.Reads().prompt_detail("q201")
    claude, gemini = d["answers"]
    assert (claude["engine"], gemini["engine"]) == ("Claude", "Gemini") and d["priority"] == "Gold"
    assert claude["claims"][0]["issue_id"] == "is_0123456789" and claude["claims"][0]["tag"] == "Outdated"
    assert [(c["owner_class"], c["domain"]) for c in claude["cited"]] == [("Editorial", "partyplanner-weekly.com"), ("Owned", "littlecaesars.com")]
    assert claude["owned_retrieved"] is True and gemini["owned_retrieved"] is False
    q2, calls2 = fake_query([])
    monkeypatch.setattr(R, "query", q2)
    assert R.Reads().prompt_detail("q999") is None
    assert R.Reads().prompt_detail("q1;drop") is None and len(calls2) == 1   # the unsafe id never reached SQL


def test_suggestions_lists_only_suggested(monkeypatch):
    q, calls = fake_query([("prompt_suggestions", [{"suggestion_id": "c001"}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().prompt_suggestions() == [{"suggestion_id": "c001"}] and "status = 'suggested'" in calls[0][0]


def test_image_path_reads_public_signals_only(monkeypatch):
    q, calls = fake_query([("v_public_signals", [{"image_uri": "/Volumes/x/goff.jpg"}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().image_path("sig_1") == "/Volumes/x/goff.jpg"
    sql, params = calls[0]
    assert "v_public_signals" in sql and "silver_signals" not in sql and ":s" in sql and params == {"s": "sig_1"}
    monkeypatch.setattr(R, "query", fake_query([])[0])
    assert R.Reads().image_path("sig_2") is None


def test_gateway_summary_survives_missing_tables(monkeypatch):
    q, _ = fake_query([("GROUP BY engine", [{"engine": "Claude", "answers": 150}]), ("v_gateway_usage", RuntimeError("no view"))])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().gateway_summary() == {"engines": [{"engine": "Claude", "answers": 150}], "answers": 150, "logged": None}


def test_insert_prompt_binds_every_value(monkeypatch):
    q, calls = fake_query([])
    monkeypatch.setattr(R, "query", q)
    R.Reads().insert_prompt({"prompt_id": "q301", "prompt_text": "Pizza for 15'; --", "cluster": "game_day_party", "priority": "Bronze",
                             "branded": False, "base_volume": 300, "calendar_tags": [], "source": "tracked", "tracked_by": "me"})
    (ins, p1), (vol, p2) = calls
    assert "Pizza for 15" not in ins and p1["prompt_text"] == "Pizza for 15'; --" and "tracked_by" not in p1
    assert vol.count("(:p, to_date(") == 12 and p2["p"] == "q301"
