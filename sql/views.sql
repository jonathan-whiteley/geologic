-- GEOlogic read views. Deployed by jobs/run_views.py (views.sql, insight_views.sql, public_views.sql in that order).
-- Share of Model math and names are unchanged from v2; everything recomputes on the tracked prompts in `prompts`.
CREATE OR REPLACE VIEW {{schema}}.v_prompts AS
SELECT prompt_id, prompt_text, cluster, priority, branded, base_volume, true AS tracked FROM {{schema}}.prompts;

-- Only ok answers of ok runs are ranked: a degraded run (probe health gate) or a failed engine in a targeted re-ask
-- never shadows the earlier ok answer for that prompt and engine (fix_results still records engine_error).
CREATE OR REPLACE VIEW {{schema}}.v_latest_responses AS
SELECT r.* EXCEPT (rn) FROM (
  SELECT pr.*, runs.started_at AS run_started_at, runs.finished_at AS run_finished_at,
         ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at DESC) rn
  FROM {{schema}}.probe_responses pr
  JOIN {{schema}}.probe_runs runs USING (run_id)
  JOIN {{schema}}.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch
  JOIN {{schema}}.prompts p ON p.prompt_id = pr.prompt_id
  WHERE runs.status = 'ok' AND pr.status = 'ok'
) r WHERE rn = 1;

CREATE OR REPLACE VIEW {{schema}}.v_latest_claims AS
SELECT c.* FROM {{schema}}.claims c JOIN (SELECT answer_id FROM {{schema}}.v_latest_responses WHERE status = 'ok') r USING (answer_id);

CREATE OR REPLACE VIEW {{schema}}.v_cluster_engine_share AS
SELECT p.cluster, r.engine,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       COUNT(*) AS n
FROM {{schema}}.v_latest_responses r JOIN {{schema}}.v_prompts p USING (prompt_id)
WHERE r.status = 'ok' AND NOT p.branded
GROUP BY p.cluster, r.engine;

-- chr(39): Spark drops a doubled apostrophe inside a string literal, so build the name with chr(39).
CREATE OR REPLACE VIEW {{schema}}.v_brand_share AS
WITH ok AS (
  SELECT r.* FROM {{schema}}.v_latest_responses r JOIN {{schema}}.v_prompts p USING (prompt_id)
  WHERE r.status = 'ok' AND NOT p.branded),
brands AS (
  SELECT 'Little Caesars' AS brand UNION ALL SELECT concat('Domino', chr(39), 's') UNION ALL
  SELECT 'Pizza Hut' UNION ALL SELECT 'Papa Johns')
SELECT brands.brand,
       AVG(COALESCE(1.0 / NULLIF(array_position(ok.brands_mentioned, brands.brand), 0), 0)) AS answer_share,
       AVG(NULLIF(array_position(ok.brands_mentioned, brands.brand), 0)) AS avg_position
FROM ok CROSS JOIN brands GROUP BY brands.brand;

-- The one view behind the header strip and the four KPI cards.
-- answer_share, mention_rate, avg_rank: unbranded prompts. Everything else: all tracked prompts.
-- last_run_at: the newest ok run in the current epoch (degraded runs are kept for audit only).
CREATE OR REPLACE VIEW {{schema}}.v_kpis AS
WITH all_ok AS (SELECT * FROM {{schema}}.v_latest_responses WHERE status = 'ok'),
unb AS (SELECT r.* FROM all_ok r JOIN {{schema}}.v_prompts p USING (prompt_id) WHERE NOT p.branded),
kpi_unb AS (
  SELECT AVG(CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END) AS answer_share,
         AVG(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) AS mention_rate,
         AVG(CASE WHEN lce_mentioned THEN lce_rank END) AS avg_rank
  FROM unb),
kpi_all AS (
  SELECT AVG(CASE WHEN cites_official THEN 1 ELSE 0 END) AS citation_rate, COUNT(*) AS answers,
         SUM(CASE WHEN lce_mentioned THEN 1 ELSE 0 END) AS mentions, COUNT(DISTINCT engine) AS engines
  FROM all_ok),
cl AS (
  SELECT SUM(CASE WHEN tag = 'Correct' THEN 1 ELSE 0 END) AS correct_claims,
         SUM(CASE WHEN tag = 'Wrong' THEN 1 ELSE 0 END) AS wrong_claims,
         SUM(CASE WHEN tag = 'Outdated' THEN 1 ELSE 0 END) AS outdated_claims,
         SUM(CASE WHEN tag = 'Unverifiable' THEN 1 ELSE 0 END) AS unverifiable_claims
  FROM {{schema}}.v_latest_claims),
cit AS (
  SELECT AVG(CASE WHEN w.owner_class = 'Owned' THEN 1 ELSE 0 END) AS owned_citation_share, COUNT(*) AS citations
  FROM (SELECT explode(cited_doc_ids) AS doc_id FROM all_ok) c JOIN {{schema}}.web_corpus w USING (doc_id)),
tp AS (SELECT COUNT(*) AS tracked_prompts FROM {{schema}}.v_prompts),
lr AS (SELECT max(r.finished_at) AS last_run_at FROM {{schema}}.probe_runs r
       JOIN {{schema}}.probe_state s ON s.id = 1 AND r.epoch = s.current_epoch WHERE r.status = 'ok')
SELECT kpi_unb.answer_share, kpi_unb.mention_rate, kpi_unb.avg_rank, kpi_all.citation_rate, cit.owned_citation_share,
       cl.correct_claims / NULLIF(cl.correct_claims + cl.wrong_claims + cl.outdated_claims, 0) AS fact_accuracy,
       coalesce(cl.correct_claims, 0) AS correct_claims, coalesce(cl.wrong_claims, 0) AS wrong_claims,
       coalesce(cl.outdated_claims, 0) AS outdated_claims, coalesce(cl.unverifiable_claims, 0) AS unverifiable_claims,
       kpi_all.answers, kpi_all.mentions, kpi_all.engines, tp.tracked_prompts, cit.citations, lr.last_run_at
FROM kpi_unb CROSS JOIN kpi_all CROSS JOIN cl CROSS JOIN cit CROSS JOIN tp CROSS JOIN lr;

CREATE OR REPLACE VIEW {{schema}}.v_source_types AS
WITH c AS (SELECT explode(cited_doc_ids) AS doc_id FROM {{schema}}.v_latest_responses WHERE status = 'ok')
SELECT w.owner_class, count(*) AS citations, count(*) / sum(count(*)) OVER () AS share
FROM c JOIN {{schema}}.web_corpus w USING (doc_id) GROUP BY w.owner_class;

CREATE OR REPLACE VIEW {{schema}}.v_top_domains AS
WITH c AS (SELECT prompt_id, explode(cited_doc_ids) AS doc_id FROM {{schema}}.v_latest_responses WHERE status = 'ok')
SELECT w.domain, w.owner_class, count(*) AS citations, count(DISTINCT c.prompt_id) AS prompts
FROM c JOIN {{schema}}.web_corpus w USING (doc_id) GROUP BY w.domain, w.owner_class;

-- Spec vocabulary over the physical tables (names kept from v2 to avoid rework).
CREATE OR REPLACE VIEW {{schema}}.sources AS
SELECT doc_id, url, domain, owner_class, last_updated, source_type, publisher, title, body, page_id FROM {{schema}}.web_corpus;

CREATE OR REPLACE VIEW {{schema}}.answers AS
SELECT answer_id, run_id, epoch, prompt_id, engine, status, answer, retrieved_doc_ids, cited_doc_ids,
       lce_mentioned, lce_rank AS position, brands_mentioned AS mentioned_brands, sentiment
FROM {{schema}}.probe_responses;
