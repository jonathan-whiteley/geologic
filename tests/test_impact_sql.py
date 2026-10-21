import json, pathlib, sys
from test_sql_v3 import _view
ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWS = ("v_phase_answers", "v_phase_metrics", "v_phase_claims", "v_movers", "v_doc_citations")


def test_impact_file_defines_the_five_views():
    for v in VIEWS:
        assert _view("sql/impact_views.sql", v)


def test_phase_answers_first_and_last_in_the_current_epoch_on_ok_runs():
    v = _view("sql/impact_views.sql", "v_phase_answers")
    assert "WHERE first_rn = 1" in v and "WHERE last_rn = 1" in v and "'before' AS phase" in v and "'after' AS phase" in v
    assert "pr.epoch = st.current_epoch" in v and "runs.status = 'ok'" in v


def test_owned_test_and_share_of_model_math_unchanged():
    m = _view("sql/impact_views.sql", "v_phase_metrics")
    assert "startswith(d, 'lce_')" in m and "startswith(d, 'lce_')" in _view("sql/impact_views.sql", "v_movers")
    assert "CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END" in m.replace("a.", "")
    assert "current_epoch" in _view("sql/impact_views.sql", "v_doc_citations")


def test_impact_file_house_rules():
    t = (ROOT / "sql/impact_views.sql").read_text()
    assert "Domino''s" not in t and "—" not in t and "–" not in t


def test_run_views_deploys_impact_fourth():
    assert '"views.sql", "insight_views.sql", "public_views.sql", "impact_views.sql"' in (ROOT / "jobs/run_views.py").read_text()


def test_genie_space_script_refuses_v2():
    sys.path.insert(0, str(ROOT / "scripts"))
    import genie_space as G
    assert G.refusal("dev", None) and G.refusal("v3", "01f1c1ad57691e9ab2457acf2bff7d78") and G.refusal("v3", None) is None
    assert G.main(["--target", "dev", "--create"]) == 1
    s = json.loads(G.serialized("jdub_demo", "geologic_v3"))
    assert "jdub_demo.geologic_v3.v_kpis" in [t["identifier"] for t in s["data_sources"]["tables"]]
    body = G.create_body("{}")
    assert body["title"] == "GEOlogic v3" and body["warehouse_id"] == "0168e23e24e6ae10"
