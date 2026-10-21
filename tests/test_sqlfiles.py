from geologic.sqlfiles import render, split_statements

def test_render_tokens():
    s = render("CREATE VIEW {{schema}}.v AS SELECT '{{usage_app}}'", catalog="jdub_demo", schema="geologic_v3")
    assert s == "CREATE VIEW jdub_demo.geologic_v3.v AS SELECT 'geologic_v3'"

def test_split_respects_dollar_blocks_and_drops_comments():
    text = ("-- header only\nCREATE VIEW a AS SELECT 1;\n\nCREATE FUNCTION f() RETURNS STRING LANGUAGE PYTHON AS $$\n"
            "x = 1;\nreturn 'a;b'\n$$;\n-- trailing comment\n")
    out = split_statements(text)
    assert len(out) == 2 and out[0] == "CREATE VIEW a AS SELECT 1" and out[1].endswith("$$") and "x = 1;" in out[1]

def test_repo_sql_files_have_no_hardcoded_v2_schema():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for p in list((root / "sql").glob("*.sql")) + [root / "genie" / "space.json", root / "jobs" / "run_views.py",
                                                     root / "jobs" / "verify_uc_functions.py"]:
        assert "jdub_demo.geologic." not in p.read_text(), p

def _split_repo(name):
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    return split_statements(render((root / "sql" / name).read_text(), catalog="jdub_demo", schema="geologic_v3"))

def test_metric_view_yaml_body_stays_intact():
    out = _split_repo("metric_views.sql")
    assert len(out) == 1
    mv = out[0]
    assert mv.startswith("CREATE OR REPLACE VIEW jdub_demo.geologic_v3.mv_answer_share") and mv.endswith("$$")
    assert mv.count("$$") == 2 and "\nversion: 1.1\n" in mv
    assert "\n  - name: Share of Model\n    expr: AVG(" in mv          # YAML indentation preserved
    assert "\nmeasures:\n" in mv and "\n  - name: Answers\n    expr: COUNT(1)\n$$" in mv

def test_uc_functions_python_body_stays_intact():
    out = _split_repo("uc_functions.sql")
    assert [s.split("(")[0].rsplit(".", 1)[1] for s in out] == ["check_exclusions", "assign_tier", "validate_jsonld", "check_facts"]
    py = out[2]
    assert py.count("$$") == 2 and py.endswith("$$") and "LANGUAGE PYTHON" in py
    assert "\n    o = json.loads(jsonld)\n" in py and "\nreturn json.dumps(errs)\n$$" in py
    assert out[3].endswith(")") and "{{schema}}" not in "".join(out)
