-- sql/views.sql : GEOlogic read views
-- Deploy via jobs/run_views.py which enforces dependency order and handles
-- the chr(39) workaround for Domino's apostrophe through the REST API.
-- v_cluster_engine_share, v_brand_share, and v_kpis join v_prompts (bank union
-- candidates) so tracked candidate prompts are included in share metrics.
-- v_prompts must be deployed before these views; jobs/run_views.py enforces that.

CREATE OR REPLACE VIEW jdub_demo.geologic.v_latest_responses AS
SELECT r.* FROM (
  SELECT pr.*, ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at DESC) rn
  FROM jdub_demo.geologic.probe_responses pr
  JOIN jdub_demo.geologic.probe_runs runs USING (run_id)
  JOIN jdub_demo.geologic.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch
) r WHERE rn = 1;

-- Joins v_prompts (bank union tracked candidates) so share metrics include
-- candidate prompts that have been probed. NOT branded filters both tables.
CREATE OR REPLACE VIEW jdub_demo.geologic.v_cluster_engine_share AS
SELECT p.cluster, r.engine,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       COUNT(*) AS n
FROM jdub_demo.geologic.v_latest_responses r JOIN jdub_demo.geologic.v_prompts p USING (prompt_id)
WHERE r.status = 'ok' AND NOT p.branded
GROUP BY p.cluster, r.engine;

-- chr(39) required: VALUES(''...'') silently drops apostrophe via REST API.
-- Joins v_prompts so tracked candidates are covered.
CREATE OR REPLACE VIEW jdub_demo.geologic.v_brand_share AS
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
FROM ok CROSS JOIN brands GROUP BY brands.brand;

-- answer_share, mention_rate, avg_rank: unbranded prompts only (v_prompts filtered).
-- citation_rate, fact_accuracy, wrong_claims, answers, mentions: all prompts.
CREATE OR REPLACE VIEW jdub_demo.geologic.v_kpis AS
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
  FROM unb),
-- Owned citation share: of every citation in ok answers, the fraction pointing at an official LCE page.
cit AS (
  SELECT AVG(CASE WHEN w.is_official THEN 1 ELSE 0 END) AS owned_citation_share
  FROM (SELECT explode(cited_doc_ids) AS doc_id FROM all_ok) c
  JOIN jdub_demo.geologic.web_corpus w USING (doc_id))
SELECT kpi_unb.answer_share, kpi_unb.mention_rate, kpi_unb.avg_rank,
       kpi_all.citation_rate, kpi_all.fact_accuracy, kpi_all.wrong_claims,
       kpi_all.answers, kpi_all.mentions, cit.owned_citation_share
FROM kpi_all CROSS JOIN kpi_unb CROSS JOIN cit;

CREATE OR REPLACE VIEW jdub_demo.geologic.v_citation_sources AS
WITH c AS (SELECT explode(cited_doc_ids) AS doc_id FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok')
SELECT w.publisher,
       CASE WHEN w.is_official THEN 'official' WHEN w.source_type = 'reddit' THEN 'forum' ELSE w.source_type END AS source_type,
       w.is_official, count(*) AS citations, count(*) / sum(count(*)) OVER () AS share
FROM c JOIN jdub_demo.geologic.web_corpus w USING (doc_id)
GROUP BY w.publisher, 2, w.is_official;

CREATE OR REPLACE VIEW jdub_demo.geologic.v_question_volume AS
WITH mult AS (
  SELECT p.prompt_id, coalesce(max(c.volume_multiplier), 1.0) AS m
  FROM jdub_demo.geologic.prompt_bank p LEFT JOIN jdub_demo.geologic.demand_calendar c
    ON array_contains(c.clusters_affected, p.cluster) AND current_timestamp() BETWEEN c.start_ts AND c.end_ts
  GROUP BY p.prompt_id),
vis AS (SELECT prompt_id, max(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) = 1 AS visible,
               max(size(filter(claims, x -> x.verdict = 'wrong'))) > 0 AS has_wrong_claim
        FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok' GROUP BY prompt_id)
SELECT p.prompt_id, p.prompt_text, p.cluster, round(p.base_volume * 10 * mult.m) AS est_monthly_volume,
       CASE WHEN p.base_volume * 10 * mult.m >= 8000 THEN 'High' WHEN p.base_volume * 10 * mult.m >= 3000 THEN 'Medium' ELSE 'Low' END AS volume_tier,
       coalesce(vis.visible, false) AS visible, coalesce(vis.has_wrong_claim, false) AS has_wrong_claim
FROM jdub_demo.geologic.prompt_bank p JOIN mult USING (prompt_id) LEFT JOIN vis USING (prompt_id);
