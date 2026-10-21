from datetime import datetime, timezone
from geologic.results import results_rows, summarize, snapshot, RESULT_COLUMNS, UPSERT_RESULT, result_values

NOW = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)
FIX = {"fix_id": "fx_1", "epoch": 2, "issue_id": "is_1", "title": "Patch our page: roundup", "tier": "T1", "asset_type": "owned_patch",
       "reviewer": "jj@x.com", "prompt_ids": ["q201"]}

def a(eng, mentioned, cited, retrieved=None, status="ok", rank=None, answer="x"):
    return {"engine": eng, "prompt_id": "q201", "status": status, "lce_mentioned": mentioned, "lce_rank": rank,
            "cited_doc_ids": cited, "retrieved_doc_ids": retrieved if retrieved is not None else cited, "answer": answer}

def c(tag, subject="party_pack", attribute="price"):
    return {"tag": tag, "subject": subject, "attribute": attribute}

BEFORE = {("q201", e): {"answer": a(e, e == "Claude", ["editorial_superbowl_roundup_2024"], rank=2 if e == "Claude" else None),
                        "claims": [c("Outdated")]} for e in ("Claude", "ChatGPT", "Gemini", "Meta AI")}
AFTER = {("q201", "Claude"): {"answer": a("Claude", True, ["lce_pg_deals_game_day"], rank=1), "claims": [c("Correct")]},
         ("q201", "ChatGPT"): {"answer": a("ChatGPT", True, ["lce_pg_deals_game_day"], rank=1), "claims": [c("Correct"), c("Wrong", "crazy_bread")]},
         ("q201", "Gemini"): {"answer": a("Gemini", False, ["comp_dominos_party_guide"], ["lce_pg_deals_game_day"]), "claims": []},
         ("q201", "Meta AI"): {"answer": a("Meta AI", None, [], [], status="engine_error"), "claims": []}}

def test_rows_per_prompt_and_engine_with_focus():
    rows = results_rows(FIX, BEFORE, AFTER, now=NOW, approved_at=NOW, elapsed_s=41.5, prompt_texts={"q201": "Super Bowl for 12"},
                        focus=("party_pack", "price"))
    by = {r["engine"]: r for r in rows}
    assert [r["engine"] for r in rows] == ["Claude", "ChatGPT", "Gemini", "Meta AI"]
    assert by["Claude"]["before_owned_cited"] is False and by["Claude"]["after_owned_cited"] is True
    assert by["ChatGPT"]["after_claim_tags"] == ["Correct"]                    # focus drops the unrelated Crazy Bread claim
    assert by["Gemini"]["after_owned_retrieved"] is True and by["Gemini"]["after_owned_cited"] is False
    assert by["Meta AI"]["status"] == "engine_error" and by["Meta AI"]["after_mentioned"] is None
    assert all(r["elapsed_s"] == 41.5 and r["prompt_text"] == "Super Bowl for 12" for r in rows)

def test_summarize_ledger_entry():
    rows = results_rows(FIX, BEFORE, AFTER, now=NOW, approved_at=NOW, focus=("party_pack", "price"))
    [e] = summarize(rows, current_epoch=2)
    p = e["prompts"][0]
    assert (p["before"]["mentioned"], p["after"]["mentioned"]) == (1, 2)
    assert (p["before"]["owned_cited"], p["after"]["owned_cited"]) == (0, 2)
    assert (p["before"]["tag"], p["after"]["tag"]) == ("Outdated", "Correct")
    assert (e["engines_answered"], e["engines_total"], e["rehearsal"]) == (3, 4, False)
    assert summarize(rows, current_epoch=3)[0]["rehearsal"] is True

def test_snapshot_without_claims_has_no_tag():
    assert snapshot(a("Claude", True, []), [])["tag"] is None

def test_rows_carry_exactly_the_fix_results_columns():
    rows = results_rows(FIX, BEFORE, AFTER, now=NOW)
    assert set(rows[0]) == set(RESULT_COLUMNS) and len(result_values(rows[0])) == UPSERT_RESULT.count("%s")
    assert "ON CONFLICT (fix_id, prompt_id, engine) DO UPDATE SET" in UPSERT_RESULT and "fix_id = EXCLUDED" not in UPSERT_RESULT
