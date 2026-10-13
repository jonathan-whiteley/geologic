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
    assert "name: Owned Citation Share" in s

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
