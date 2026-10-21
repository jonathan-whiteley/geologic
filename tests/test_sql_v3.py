import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _view(path, name):
    s = (ROOT / path).read_text()
    m = re.search(r"CREATE OR REPLACE VIEW \S*\." + name + r"\b.*?;\s*$", s, re.S | re.M)
    assert m, f"{name} not found in {path}"
    return m.group(0)

def test_kpis_is_the_one_view_for_every_count():
    v = _view("sql/views.sql", "v_kpis")
    for col in ("answer_share", "mention_rate", "owned_citation_share", "fact_accuracy", "wrong_claims", "outdated_claims",
                "answers", "engines", "tracked_prompts", "last_run_at"):
        assert col in v, col
    assert "owner_class = 'Owned'" in v and "v_latest_claims" in v and "'Outdated'" in v

def test_share_of_model_math_is_unchanged():
    for name in ("v_kpis", "v_cluster_engine_share"):
        assert "CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END" in _view("sql/views.sql", name).replace("r.", "")
    assert "1.0 / NULLIF(array_position(ok.brands_mentioned, brands.brand), 0)" in _view("sql/views.sql", "v_brand_share")

def test_prompt_status_columns_and_sources():
    v = _view("sql/insight_views.sql", "v_prompt_status")
    for col in ("priority", "est_monthly_searches", "engines_owned_cited", "outdated_claims", "moment_id"):
        assert col in v
    assert "owner_class" in _view("sql/views.sql", "v_source_types") and "domain" in _view("sql/views.sql", "v_top_domains")

def test_removed_views_are_gone():
    text = " ".join((ROOT / p).read_text() for p in ("sql/views.sql", "sql/insight_views.sql", "sql/public_views.sql"))
    # tracked_prompts is not banned: it is a v_kpis column (the header strip count)
    for gone in ("v_citation_sources", "v_question_volume", "v_theme_sentiment", "prompt_bank", "prompt_candidates"):
        assert gone not in text, gone

def test_dominos_literal_uses_chr39():
    for p in ("sql/views.sql", "sql/public_views.sql"):
        assert "Domino''s" not in (ROOT / p).read_text()

# Task 3 review carry-over: probe_runs.status is 'degraded' for unhealthy runs. Only 'ok' runs may feed the latest
# answer per prompt and engine, the weekly history and the last run time, and the filter must sit before the
# ROW_NUMBER ranking, so a newer degraded run never shadows an earlier ok run.
def test_only_ok_runs_feed_latest_weekly_and_last_run():
    latest = _view("sql/views.sql", "v_latest_responses")
    assert "WHERE runs.status = 'ok'" in latest and latest.index("runs.status = 'ok'") < latest.index("WHERE rn = 1")
    weekly = _view("sql/public_views.sql", "v_answer_share_weekly")
    assert "runs.status = 'ok'" in weekly and weekly.index("runs.status = 'ok'") < weekly.index("ROW_NUMBER")
    lr = re.search(r"lr AS \((.*?)\)\s*SELECT", _view("sql/views.sql", "v_kpis"), re.S).group(1)
    assert "r.status = 'ok'" in lr and "finished_at" in lr

def test_no_view_reads_retired_probe_columns():
    for p in ("sql/views.sql", "sql/insight_views.sql", "sql/public_views.sql", "sql/metric_views.sql"):
        t = (ROOT / p).read_text()
        assert "verdict" not in t and "answer_themes" not in t and "is_official" not in t, p

# Moved from tests/test_sql_v2.py. Task 13 updated the two Genie pins to the v3 questions and tables.
def test_metric_view_uses_share_of_model_name():
    s = (ROOT / "sql/metric_views.sql").read_text()
    assert "name: Share of Model" in s and "name: Answer Share" not in s and "Owned Citation Share" not in s

def test_prompt_status_exposes_branded():
    assert "p.branded" in _view("sql/insight_views.sql", "v_prompt_status")

def test_genie_space_says_share_of_model():
    d = json.loads((ROOT / "genie/space.json").read_text())
    qs = [q["question"][0] for q in d["config"]["sample_questions"]]
    assert qs == ["Which engine still states the old Party Pack price?",
                  "What is our Share of Model vs Domino's on game-day prompts?",
                  "Which unowned domains are cited most on our Gold prompts?"]
    text = json.dumps(d["instructions"])
    assert "Share of Model" in text and "Answer Share" not in text

def test_genie_space_has_brand_share_for_competitors():
    d = json.loads((ROOT / "genie/space.json").read_text())
    ids = [t["identifier"] for t in d["data_sources"]["tables"]]
    assert "{{schema}}.v_brand_share" in ids and "{{schema}}.v_prompts" in ids and ids == sorted(ids)
    assert ids == ["{{schema}}." + t for t in ("brand_facts", "issues", "mv_answer_share", "prompts", "sources", "v_answer_share_weekly",
                                               "v_brand_share", "v_kpis", "v_latest_claims", "v_latest_responses", "v_prompt_status",
                                               "v_prompts", "v_source_types", "v_top_domains")]
    text = " ".join(d["instructions"]["text_instructions"][0]["content"])
    assert "v_brand_share" in text and "array_position(brands_mentioned" in text and "Domino's" in text
    assert "concat('Domino', chr(39), 's')" in text and "Domino''s" not in text

def test_gateway_view_dedupes_served_entities():
    v = _view("sql/gateway_views.sql", "v_gateway_usage")
    assert "(SELECT DISTINCT served_entity_id, endpoint_name FROM system.serving.served_entities)" in v

def test_no_dashes_in_sql_and_genie():
    for p in ("sql/views.sql", "sql/insight_views.sql", "sql/public_views.sql", "sql/metric_views.sql", "sql/impact_views.sql",
              "genie/space.json"):
        t = (ROOT / p).read_text()
        assert "\u2014" not in t and "\u2013" not in t, p


def test_metric_view_v3_measures_and_priority():
    s = (ROOT / "sql/metric_views.sql").read_text()
    assert "name: Visibility" in s and "name: Priority" in s and "p.priority" in s and "Share of Voice, weighted by rank" in s


def test_genie_space_v3_instructions():
    text = " ".join(json.loads((ROOT / "genie/space.json").read_text())["instructions"]["text_instructions"][0]["content"])
    for needle in ("Share of Voice, weighted by rank: being named first counts most.", "F13 (24.99)", "F12 (29.99)",
                   "owner_class <> 'Owned'", "cluster game_day_party", "Issues are in issues ordered by rank.",
                   "v_public_signals", "Claude, ChatGPT, Gemini, Meta AI"):
        assert needle in text, needle
    assert "gold_opportunities" not in text and "verdict" not in text


def test_latest_responses_ranks_only_ok_answers():   # a failed engine in a targeted re-ask keeps its earlier ok answer
    latest = _view("sql/views.sql", "v_latest_responses")
    assert "pr.status = 'ok'" in latest and latest.index("pr.status = 'ok'") < latest.index("WHERE rn = 1")
