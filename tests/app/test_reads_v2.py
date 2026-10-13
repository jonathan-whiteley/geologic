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
                return rows
        return []
    return q, calls

def test_inventory_sorted_by_volume(monkeypatch):
    q, calls = fake_query([("v_prompt_status", [{"prompt_id": "q001"}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().prompt_inventory() == [{"prompt_id": "q001"}]
    assert "ORDER BY avg_monthly_volume DESC" in calls[0][0] and "branded" in calls[0][0]

def test_evidence_unknown_opp_is_none(monkeypatch):
    q, _ = fake_query([("gold_opportunities", [])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().opportunity_evidence("opp_x") is None

def test_evidence_empty_opp_runs_no_in_list(monkeypatch):  # Review Focus 1
    opp = {"opp_id": "opp_1", "page_id": "pg_menu", "prompt_ids": [], "item_id": None, "signal_ids": []}
    q, calls = fake_query([("gold_opportunities", [opp])])
    monkeypatch.setattr(R, "query", q)
    ev = R.Reads().opportunity_evidence("opp_1")
    assert ev == {"opp_id": "opp_1", "page_id": "pg_menu", "wrong_claims": [], "truth": None, "cited_instead": [], "signal": None}
    assert len(calls) == 1 and all("IN ()" not in s for s, _ in calls)

def test_evidence_full(monkeypatch):
    opp = {"opp_id": "opp_1", "page_id": "pg_deals", "prompt_ids": ["q001", "bad id;"], "item_id": "classic_pep", "signal_ids": ["s9"]}
    q, calls = fake_query([
        ("gold_opportunities", [opp]),
        ("explode(r.claims)", [{"engine": "Llama", "item": "Classic Pepperoni", "price": "$5.55"}]),
        # v_public_signals before menu_items: the signal query also joins menu_items
        ("v_public_signals", [{"signal_id": "s9", "author": "@goff", "text": "t", "persona_name": "Jared Goff",
                               "menu_item_name": "Deep!Deep! Dish", "image_uri": "/Volumes/x/goff.jpg"}]),
        ("menu_items", [{"name": "Classic Pepperoni", "price": 6.49}]),
        ("NOT w.is_official", [{"publisher": "reddit.com", "source_type": "forum", "citations": 7}]),
    ])
    monkeypatch.setattr(R, "query", q)
    monkeypatch.setattr(R, "credit_for", lambda uri: "Photo: AP")
    ev = R.Reads().opportunity_evidence("opp_1")
    assert ev["wrong_claims"][0]["engine"] == "Llama"
    assert ev["truth"] == {"name": "Classic Pepperoni", "price": 6.49}
    assert ev["cited_instead"][0]["publisher"] == "reddit.com"
    assert ev["signal"]["image_url"] == "/api/signals/s9/image" and ev["signal"]["image_credit"] == "Photo: AP"
    assert "image_uri" not in ev["signal"]
    joined = " ".join(s for s, _ in calls)
    assert "'q001'" in joined and "bad id" not in joined  # unsafe ids are dropped, never inlined

def test_gateway_summary_counts_usage(monkeypatch):
    q, _ = fake_query([
        ("GROUP BY engine", [{"engine": "Claude", "answers": 150}, {"engine": "Meta AI", "answers": 148}]),
        ("v_gateway_usage", [{"n": 1200}]),
    ])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().gateway_summary() == {"engines": [{"engine": "Claude", "answers": 150}, {"engine": "Meta AI", "answers": 148}],
                                           "answers": 298, "logged": 1200}

def test_gateway_summary_survives_missing_tables(monkeypatch):  # Review Focus 2
    q, _ = fake_query([("GROUP BY engine", [{"engine": "Claude", "answers": 150}]), ("v_gateway_usage", RuntimeError("no view"))])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().gateway_summary()["logged"] is None

def test_gateway_summary_no_tables_is_none(monkeypatch):
    q, _ = fake_query([("GROUP BY engine", []), ("v_gateway_usage", [{"n": None}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().gateway_summary() == {"engines": [], "answers": 0, "logged": None}

def test_opportunities_reasoning_says_share_of_model(monkeypatch):
    q, _ = fake_query([("gold_opportunities", [{"opp_id": "o", "reasoning": "Answer Share 0.07 in comparison across 8 answers."}])])
    monkeypatch.setattr(R, "query", q)
    assert R.Reads().opportunities()[0]["reasoning"] == "Share of Model 0.07 in comparison across 8 answers."
