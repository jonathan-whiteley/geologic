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
    assert R.Reads().opportunities()[0]["reasoning"] == "Share of Model 0.07 in Comparisons across 8 answers."

# P1: before_after picks the (prompt, engine) pair that moved most, not prompt_ids[0] on Claude.
def _ba_row(pid, engine, phase, answer, mentioned=False, rank=None, wrong=0, cited=(), text=None):
    return {"prompt_id": pid, "engine": engine, "phase": phase, "answer": answer, "cited": list(cited),
            "lce_mentioned": mentioned, "lce_rank": rank, "wrong": wrong, "prompt_text": text or f"text {pid}"}

def _ba(monkeypatch, rows, ids):
    q, calls = fake_query([("probe_responses", rows)])
    monkeypatch.setattr(R, "query", q)
    return R.Reads().before_after(ids), calls

def test_before_after_picks_most_improved_pair(monkeypatch):
    rows = [_ba_row("q006", "Claude", "before", "Domino's only"), _ba_row("q006", "Claude", "after", "Domino's only"),
            _ba_row("q111", "Claude", "before", "Pizza Hut first [blog_x]", cited=["blog_x"]),
            _ba_row("q111", "Claude", "after", "Little Caesars first", True, 1, cited=["lce_pg_deals_game_day"],
                    text="Game day food ideas for a crowd"),
            _ba_row("q090", "Gemini", "before", "no LCE"), _ba_row("q090", "Gemini", "after", "LCE third", True, 3)]
    ba, calls = _ba(monkeypatch, rows, ["q006", "q111", "q090"])
    assert ba["prompt_id"] == "q111" and ba["engine"] == "Claude" and ba["prompt_text"] == "Game day food ideas for a crowd"
    assert ba["before"] == {"answer": "Pizza Hut first [blog_x]", "cited": ["blog_x"]}
    assert ba["after"] == {"answer": "Little Caesars first", "cited": ["lce_pg_deals_game_day"]}
    assert len(calls) == 1 and "'q006','q111','q090'" in calls[0][0] and "first_rn" in calls[0][0]

def test_before_after_scores_rank_and_wrong_claims(monkeypatch):
    rows = [_ba_row("q001", "Claude", "before", "a", True, 3), _ba_row("q001", "Claude", "after", "b", True, 2),  # +1
            _ba_row("q002", "Meta AI", "before", "c", True, 4, wrong=3), _ba_row("q002", "Meta AI", "after", "d", True, 3, wrong=1)]  # +3
    ba, _ = _ba(monkeypatch, rows, ["q001", "q002"])
    assert (ba["prompt_id"], ba["engine"]) == ("q002", "Meta AI")

def test_before_after_ties_break_by_engine_order_then_prompt(monkeypatch):
    rows = []
    for pid, eng in (("q002", "Meta AI"), ("q002", "ChatGPT"), ("q003", "Gemini"), ("q001", "ChatGPT")):
        rows += [_ba_row(pid, eng, "before", "x"), _ba_row(pid, eng, "after", "y", True, 1)]
    ba, _ = _ba(monkeypatch, rows, ["q001", "q002", "q003"])
    assert (ba["prompt_id"], ba["engine"]) == ("q001", "ChatGPT")

def test_before_after_falls_back_to_most_wrong_claims_then_first_prompt(monkeypatch):
    flat = [_ba_row("q001", "Claude", "before", "a"), _ba_row("q001", "Claude", "after", "a"),
            _ba_row("q002", "Gemini", "before", "w", wrong=2), _ba_row("q002", "Gemini", "after", "w", wrong=2)]
    ba, _ = _ba(monkeypatch, flat, ["q001", "q002"])
    assert (ba["prompt_id"], ba["engine"]) == ("q002", "Gemini")
    clean = [_ba_row("q002", "Gemini", "before", "a"), _ba_row("q002", "Gemini", "after", "a"),
             _ba_row("q001", "Claude", "before", "b"), _ba_row("q001", "Claude", "after", "b")]
    ba, _ = _ba(monkeypatch, clean, ["q001", "q002"])
    assert (ba["prompt_id"], ba["engine"]) == ("q001", "Claude")

def test_before_after_worse_answer_is_not_an_improvement(monkeypatch):
    rows = [_ba_row("q002", "ChatGPT", "before", "LCE first", True, 1), _ba_row("q002", "ChatGPT", "after", "gone"),
            _ba_row("q001", "Claude", "before", "a"), _ba_row("q001", "Claude", "after", "a")]
    ba, _ = _ba(monkeypatch, rows, ["q001", "q002"])
    assert (ba["prompt_id"], ba["engine"]) == ("q001", "Claude")

def test_before_after_none_without_pairs_or_safe_ids(monkeypatch):
    assert _ba(monkeypatch, [], ["q001"])[0] is None
    ba, calls = _ba(monkeypatch, [], ["bad id;"])
    assert ba is None and calls == []
    assert R.Reads().before_after([]) is None
    half = [_ba_row("q001", "Claude", "before", "a")]  # only one phase: no pair
    assert _ba(monkeypatch, half, ["q001"])[0] is None

# O2: cluster keys in stored reasoning read as human labels.
def test_opportunities_reasoning_uses_cluster_labels(monkeypatch):
    q, _ = fake_query([("gold_opportunities", [
        {"opp_id": "a", "reasoning": "Share of Model 0.08 in game_day_party across 84 answers."},
        {"opp_id": "b", "reasoning": "Official citation rate 0.20 in sponsorship with mention rate 0.90."},
        {"opp_id": "c", "reasoning": "3 of 9 price claims about Classic Pepperoni are wrong."}])])
    monkeypatch.setattr(R, "query", q)
    out = [r["reasoning"] for r in R.Reads().opportunities()]
    assert out == ["Share of Model 0.08 in Game-day / party sizing across 84 answers.",
                   "Official citation rate 0.20 in Sponsorship (NFL) with mention rate 0.90.",
                   "3 of 9 price claims about Classic Pepperoni are wrong."]
