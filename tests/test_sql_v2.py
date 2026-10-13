import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _view(path, name):
    s = (ROOT / path).read_text()
    m = re.search(r"CREATE OR REPLACE VIEW \S*\." + name + r"\b.*?;\s*$", s, re.S | re.M)
    assert m, f"{name} not found in {path}"
    return m.group(0)

def test_kpis_has_owned_citation_share():
    v = _view("sql/views.sql", "v_kpis")
    assert "owned_citation_share" in v and "is_official" in v

def test_prompt_status_exposes_branded():
    v = _view("sql/insight_views.sql", "v_prompt_status")
    assert "p.branded" in v

def test_metric_view_uses_share_of_model_name():
    s = (ROOT / "sql/metric_views.sql").read_text()
    assert "name: Share of Model" in s and "name: Answer Share" not in s
    assert "Owned Citation Share" not in s

def test_genie_space_says_share_of_model():
    d = json.loads((ROOT / "genie/space.json").read_text())
    qs = [q["question"][0] for q in d["config"]["sample_questions"]]
    assert qs == ["Which question cluster has the lowest Share of Model?",
                  "Which engine still gets our prices wrong?",
                  "What are the top 3 opportunities and why?"]
    text = json.dumps(d["instructions"])
    assert "Share of Model" in text
    assert "Answer Share" not in text

def test_no_dashes_in_changed_sql_comments():
    for p in ("sql/views.sql", "sql/insight_views.sql", "sql/metric_views.sql", "genie/space.json"):
        assert "—" not in (ROOT / p).read_text() and "–" not in (ROOT / p).read_text(), p

def test_genie_space_has_brand_share_for_competitors():  # G3
    d = json.loads((ROOT / "genie/space.json").read_text())
    ids = [t["identifier"] for t in d["data_sources"]["tables"]]
    assert "jdub_demo.geologic.v_brand_share" in ids and ids == sorted(ids)
    text = " ".join(d["instructions"]["text_instructions"][0]["content"])
    assert "v_brand_share" in text and "array_position(brands_mentioned" in text and "Domino's" in text
    # the per-engine formula needs v_prompts.branded, so v_prompts is a data source too
    assert "v_prompts" in text and "jdub_demo.geologic.v_prompts" in ids
    # 'Domino''s' parses as 'Dominos' in Databricks SQL and never matches; use the chr(39) form
    assert "concat('Domino', chr(39), 's')" in text
    assert "Domino''s" not in text

def test_gateway_view_dedupes_served_entities():  # S2
    for path in ("sql/gateway_views.sql", "sql/v2_data_fixes.sql"):
        v = _view(path, "v_gateway_usage")
        assert "(SELECT DISTINCT served_entity_id, endpoint_name FROM system.serving.served_entities)" in v, path

def test_v2_data_fixes_sql():  # O1, O2, P2
    s = (ROOT / "sql/v2_data_fixes.sql").read_text()
    assert "UPDATE jdub_demo.geologic.gold_opportunities SET reasoning = replace(reasoning, 'Answer Share', 'Share of Model') " \
           "WHERE reasoning LIKE '%Answer Share%';" in s
    from geologic.datagen.reference import CLUSTER_LABELS
    for key, label in CLUSTER_LABELS.items():
        assert f"' in {key} across', ' in {label} across'" in s and f"' in {key} with', ' in {label} with'" in s, key
    assert "ALTER TABLE proof_results ADD COLUMN IF NOT EXISTS prompt_text TEXT;" in s
    assert "ALTER TABLE proof_results ADD COLUMN IF NOT EXISTS prompt_text TEXT;" in (ROOT / "sql/lakebase_schema.sql").read_text()
    assert "—" not in s and "–" not in s
