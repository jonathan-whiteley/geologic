"""Deploys all GEOlogic SQL views in dependency order.

Deployment order enforced here:
  1. v_latest_responses   -- no view deps
  2. v_prompts            -- no view deps (bank union candidates with branded)
  3. v_cluster_engine_share, v_brand_share, v_kpis  -- depend on v_prompts
  4. v_citation_sources, v_question_volume           -- no v_prompts dep
  5. v_prompt_status, v_theme_sentiment, v_leaderboard

v_prompts is physically defined in sql/insight_views.sql but deployed here
before the share views so views.sql can reference it without a cycle.

chr(39) is used for Domino apostrophe: the Databricks SQL REST API silently
drops the apostrophe when VALUES(''...'') is used.
"""
import sys, os

# Serverless spark_python_task exec does not set __file__; cwd is script workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()


def run(sql: str, label: str) -> None:
    spark.sql(sql)
    print(f"  OK  {label}")


# 1. v_latest_responses
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_latest_responses AS
SELECT r.* FROM (
  SELECT pr.*, ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at DESC) rn
  FROM jdub_demo.geologic.probe_responses pr
  JOIN jdub_demo.geologic.probe_runs runs USING (run_id)
  JOIN jdub_demo.geologic.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch
) r WHERE rn = 1""", "v_latest_responses")

# 2. v_prompts (insight_views.sql section, deployed early so share views can reference it)
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_prompts AS
SELECT prompt_id, prompt_text, cluster, base_volume, true AS tracked, branded
FROM jdub_demo.geologic.prompt_bank
UNION ALL
SELECT c.prompt_id, c.prompt_text, c.cluster, c.base_volume, t.prompt_id IS NOT NULL AS tracked, c.branded
FROM jdub_demo.geologic.prompt_candidates c
LEFT JOIN (SELECT DISTINCT prompt_id FROM jdub_demo.geologic.tracked_prompts) t USING (prompt_id)""",
    "v_prompts")

# 3a. v_cluster_engine_share -- joins v_prompts for bank+candidates
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_cluster_engine_share AS
SELECT p.cluster, r.engine,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       COUNT(*) AS n
FROM jdub_demo.geologic.v_latest_responses r JOIN jdub_demo.geologic.v_prompts p USING (prompt_id)
WHERE r.status = 'ok' AND NOT p.branded
GROUP BY p.cluster, r.engine""", "v_cluster_engine_share")

# 3b. v_brand_share -- chr(39) for apostrophe; joins v_prompts
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_brand_share AS
WITH ok AS (
  SELECT r.* FROM jdub_demo.geologic.v_latest_responses r
  JOIN jdub_demo.geologic.v_prompts p USING (prompt_id)
  WHERE r.status = 'ok' AND NOT p.branded),
brands AS (
  SELECT 'Little Caesars' AS brand UNION ALL
  SELECT concat('Domino', chr(39), 's') UNION ALL
  SELECT 'Pizza Hut' UNION ALL
  SELECT 'Papa Johns')
SELECT brands.brand,
       AVG(COALESCE(1.0 / NULLIF(array_position(ok.brands_mentioned, brands.brand), 0), 0)) AS answer_share
FROM ok CROSS JOIN brands GROUP BY brands.brand""", "v_brand_share")

# 3c. v_kpis -- answer_share/mention_rate/avg_rank: unbranded; rest: all prompts
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_kpis AS
WITH all_ok AS (SELECT * FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok'),
unb AS (
  SELECT r.* FROM jdub_demo.geologic.v_latest_responses r
  JOIN jdub_demo.geologic.v_prompts p USING (prompt_id)
  WHERE r.status = 'ok' AND NOT p.branded),
kpi_all AS (
  SELECT AVG(CASE WHEN cites_official THEN 1 ELSE 0 END) AS citation_rate,
         SUM(size(filter(claims, c -> c.verdict = 'correct'))) /
           NULLIF(SUM(size(filter(claims, c -> c.verdict IN ('correct', 'wrong')))), 0) AS fact_accuracy,
         SUM(size(filter(claims, c -> c.verdict = 'wrong'))) AS wrong_claims,
         COUNT(*) AS answers,
         SUM(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) AS mentions
  FROM all_ok),
kpi_unb AS (
  SELECT AVG(CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END) AS answer_share,
         AVG(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) AS mention_rate,
         AVG(CASE WHEN lce_mentioned THEN lce_rank END) AS avg_rank
  FROM unb)
SELECT kpi_unb.answer_share, kpi_unb.mention_rate, kpi_unb.avg_rank,
       kpi_all.citation_rate, kpi_all.fact_accuracy, kpi_all.wrong_claims,
       kpi_all.answers, kpi_all.mentions
FROM kpi_all CROSS JOIN kpi_unb""", "v_kpis")

# 4. v_citation_sources, v_question_volume
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_citation_sources AS
WITH c AS (SELECT explode(cited_doc_ids) AS doc_id FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok')
SELECT w.publisher,
       CASE WHEN w.is_official THEN 'official' WHEN w.source_type = 'reddit' THEN 'forum' ELSE w.source_type END AS source_type,
       w.is_official, count(*) AS citations, count(*) / sum(count(*)) OVER () AS share
FROM c JOIN jdub_demo.geologic.web_corpus w USING (doc_id)
GROUP BY w.publisher, 2, w.is_official""", "v_citation_sources")

run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_question_volume AS
WITH mult AS (
  SELECT p.prompt_id, coalesce(max(c.volume_multiplier), 1.0) AS m
  FROM jdub_demo.geologic.prompt_bank p LEFT JOIN jdub_demo.geologic.demand_calendar c
    ON array_contains(c.clusters_affected, p.cluster) AND current_timestamp() BETWEEN c.start_ts AND c.end_ts
  GROUP BY p.prompt_id),
vis AS (SELECT prompt_id, max(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) = 1 AS visible,
               max(size(filter(claims, x -> x.verdict = 'wrong'))) > 0 AS has_wrong_claim
        FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok' GROUP BY prompt_id)
SELECT p.prompt_id, p.prompt_text, p.cluster, round(p.base_volume * 10 * mult.m) AS est_monthly_volume,
       CASE WHEN p.base_volume * 10 * mult.m >= 8000 THEN 'High'
            WHEN p.base_volume * 10 * mult.m >= 3000 THEN 'Medium' ELSE 'Low' END AS volume_tier,
       coalesce(vis.visible, false) AS visible, coalesce(vis.has_wrong_claim, false) AS has_wrong_claim
FROM jdub_demo.geologic.prompt_bank p JOIN mult USING (prompt_id) LEFT JOIN vis USING (prompt_id)""",
    "v_question_volume")

# 5. insight_views.sql views (v_prompt_status, v_theme_sentiment, v_leaderboard)
run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_prompt_status AS
WITH r AS (SELECT * FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok'),
v AS (SELECT prompt_id, avg(est_volume) AS avg_monthly_volume FROM jdub_demo.geologic.question_volume_monthly GROUP BY prompt_id),
ft AS (SELECT prompt_id, min(started_at) AS first_tracked, max(finished_at) AS updated_at
       FROM jdub_demo.geologic.probe_runs pr LATERAL VIEW explode(pr.prompt_ids) t AS prompt_id GROUP BY prompt_id)
SELECT p.prompt_id, p.prompt_text, p.cluster, p.tracked, round(v.avg_monthly_volume) AS avg_monthly_volume,
       CASE WHEN v.avg_monthly_volume >= 8000 THEN 'High' WHEN v.avg_monthly_volume >= 3000 THEN 'Medium' ELSE 'Low' END AS volume_tier,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       SUM(CASE WHEN r.lce_mentioned THEN 1 ELSE 0 END) AS engines_naming,
       COUNT(r.engine) AS engines_answered,
       MAX(size(filter(r.claims, x -> x.verdict = 'wrong'))) > 0 AS has_wrong_claim,
       ft.first_tracked, ft.updated_at
FROM jdub_demo.geologic.v_prompts p LEFT JOIN v USING (prompt_id) LEFT JOIN r USING (prompt_id) LEFT JOIN ft USING (prompt_id)
GROUP BY p.prompt_id, p.prompt_text, p.cluster, p.tracked, v.avg_monthly_volume, ft.first_tracked, ft.updated_at""",
    "v_prompt_status")

run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_theme_sentiment AS
SELECT theme, count(*) AS answers,
       avg(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS pct_positive,
       avg(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS pct_negative,
       min_by(substr(answer, 1, 90), CASE WHEN sentiment = 'negative' THEN 0 ELSE 1 END * 1000 + length(answer)) AS sample_quote
FROM jdub_demo.geologic.answer_themes GROUP BY theme""", "v_theme_sentiment")

run("""CREATE OR REPLACE VIEW jdub_demo.geologic.v_leaderboard AS
WITH cites AS (SELECT explode(cited_doc_ids) AS doc_id FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok'),
by_brand AS (SELECT b.brand, count(*) AS n FROM cites JOIN jdub_demo.geologic.doc_brand b USING (doc_id) GROUP BY b.brand),
total AS (SELECT count(*) AS n FROM cites)
SELECT s.brand, s.answer_share, coalesce(bb.n / t.n, 0) AS citation_share
FROM jdub_demo.geologic.v_brand_share s LEFT JOIN by_brand bb USING (brand) CROSS JOIN total t""",
    "v_leaderboard")

print("All views deployed.")
