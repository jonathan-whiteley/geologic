-- Impact: before = the first answer per prompt and engine in the current epoch (the baseline Reset restores), after = the latest.
-- Only ok runs count (a degraded run never becomes before or after), as in v_latest_responses. Owned doc ids start with lce_.
CREATE OR REPLACE VIEW {{schema}}.v_phase_answers AS
WITH e AS (
  SELECT pr.*, runs.started_at,
         ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at) AS first_rn,
         ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at DESC) AS last_rn
  FROM {{schema}}.probe_responses pr
  JOIN {{schema}}.probe_runs runs USING (run_id)
  JOIN {{schema}}.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch
  JOIN {{schema}}.prompts p ON p.prompt_id = pr.prompt_id
  WHERE pr.status = 'ok' AND runs.status = 'ok')
SELECT 'before' AS phase, * FROM e WHERE first_rn = 1
UNION ALL
SELECT 'after' AS phase, * FROM e WHERE last_rn = 1;

CREATE OR REPLACE VIEW {{schema}}.v_phase_metrics AS
SELECT a.phase, COUNT(*) AS answers,
       SUM(CASE WHEN a.lce_mentioned THEN 1 ELSE 0 END) AS mention_lce,
       SUM(CASE WHEN exists(a.cited_doc_ids, d -> startswith(d, 'lce_')) THEN 1 ELSE 0 END) AS cite_lce,
       SUM(CASE WHEN a.lce_rank = 1 THEN 1 ELSE 0 END) AS pick_lce_first,
       SUM(CASE WHEN exists(a.retrieved_doc_ids, d -> startswith(d, 'lce_')) THEN 1 ELSE 0 END) AS owned_retrieved,
       AVG(CASE WHEN NOT p.branded THEN CASE WHEN a.lce_mentioned AND a.lce_rank > 0 THEN 1.0 / a.lce_rank ELSE 0 END END) AS answer_share,
       AVG(CASE WHEN NOT p.branded THEN CASE WHEN a.lce_mentioned THEN 1 ELSE 0 END END) AS mention_rate,
       AVG(CASE WHEN a.lce_mentioned THEN a.lce_rank END) AS avg_rank
FROM {{schema}}.v_phase_answers a JOIN {{schema}}.v_prompts p USING (prompt_id)
GROUP BY a.phase;

CREATE OR REPLACE VIEW {{schema}}.v_phase_claims AS
SELECT a.phase, SUM(CASE WHEN c.tag IN ('Wrong', 'Outdated') THEN 1 ELSE 0 END) AS wrong_or_outdated,
       SUM(CASE WHEN c.tag = 'Correct' THEN 1 ELSE 0 END) AS correct
FROM {{schema}}.v_phase_answers a JOIN {{schema}}.claims c USING (answer_id)
GROUP BY a.phase;

CREATE OR REPLACE VIEW {{schema}}.v_movers AS
SELECT a.prompt_id, p.prompt_text, p.cluster,
       SUM(CASE WHEN a.phase = 'before' AND a.lce_mentioned THEN 1 ELSE 0 END) AS naming_before,
       SUM(CASE WHEN a.phase = 'after' AND a.lce_mentioned THEN 1 ELSE 0 END) AS naming_after,
       SUM(CASE WHEN a.phase = 'before' AND exists(a.cited_doc_ids, d -> startswith(d, 'lce_')) THEN 1 ELSE 0 END) AS owned_cited_before,
       SUM(CASE WHEN a.phase = 'after' AND exists(a.cited_doc_ids, d -> startswith(d, 'lce_')) THEN 1 ELSE 0 END) AS owned_cited_after
FROM {{schema}}.v_phase_answers a JOIN {{schema}}.v_prompts p USING (prompt_id)
GROUP BY a.prompt_id, p.prompt_text, p.cluster;

-- Citations of one doc per probe run in the current epoch (the Impact citation tracker). Subquery form: explode first,
-- then join the runs, so no LATERAL VIEW follows a join.
CREATE OR REPLACE VIEW {{schema}}.v_doc_citations AS
SELECT t.doc_id, t.run_id, runs.started_at, count(*) AS citations, count(DISTINCT t.prompt_id) AS prompts,
       collect_set(t.prompt_id) AS prompt_ids
FROM (SELECT run_id, prompt_id, explode(cited_doc_ids) AS doc_id FROM {{schema}}.probe_responses
      WHERE status = 'ok' AND epoch = (SELECT current_epoch FROM {{schema}}.probe_state WHERE id = 1)) t
JOIN {{schema}}.probe_runs runs USING (run_id)
WHERE runs.status = 'ok'
GROUP BY t.doc_id, t.run_id, runs.started_at;
