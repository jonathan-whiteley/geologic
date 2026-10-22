import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from datetime import datetime, timezone
from backend.warehouse_store import insert_batches, insert_rows

def test_insert_rows_binds_scalars_and_json_arrays():
    sql, params = insert_rows("jdub_demo.geologic_v3.claims", [{"claim_id": "c1", "tag": "Correct", "ids": ["a", "b"]},
                                                               {"claim_id": "c2", "tag": "Wrong", "ids": []}], array_cols={"ids"})
    assert sql.startswith("INSERT INTO jdub_demo.geologic_v3.claims (claim_id, tag, ids) VALUES")
    assert "from_json(:r0_ids, 'array<string>')" in sql and ":r1_tag" in sql
    assert params["r0_ids"] == '["a", "b"]' and params["r1_claim_id"] == "c2"

def test_timestamps_and_batches_stay_under_the_param_cap():
    t = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)
    sql, params = insert_rows("x.y.probe_runs", [{"run_id": "r", "started_at": t}], set(), ts_cols={"started_at"})
    assert "to_timestamp(:r0_started_at)" in sql and params["r0_started_at"] == "2026-10-22T13:00:00+00:00"
    rows = [{f"c{j}": j for j in range(13)} for _ in range(40)]
    batches = insert_batches("x.y.claims", rows, set())
    assert len(batches) > 1 and all(len(p) <= 250 for _, p in batches) and sum(len(p) for _, p in batches) == 40 * 13

def test_response_rows_drop_the_ui_only_cited_chips():
    from backend.warehouse_store import response_rows
    a = [{"answer_id": "a1", "cited_doc_ids": ["d1"], "cited": [{"doc_id": "d1"}]}]
    rows = response_rows(a)
    assert rows == [{"answer_id": "a1", "cited_doc_ids": ["d1"]}] and "cited" in a[0]   # the caller's answers keep their chips
    sql, _ = insert_batches("x.y.probe_responses", rows, {"cited_doc_ids"})[0]
    assert "cited," not in sql and "cited)" not in sql
