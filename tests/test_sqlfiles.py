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
