CREATE OR REPLACE VIEW jdub_demo.geologic.v_public_signals AS
SELECT signal_id, source_type, ingested_at, author, reach, velocity, text, page, hits, image_uri,
       topic, sentiment, menu_item_id, persona_id, image_match_score, resolution_confidence
FROM jdub_demo.geologic.silver_signals WHERE NOT quarantined;

-- Live weeks use the SAME Answer Share definition as v_kpis / v_brand_share: for each live week, the
-- latest response per prompt and engine as of that week's end (v_latest_responses semantics), unbranded
-- prompts only (v_prompts NOT branded). The last live week therefore equals v_kpis.answer_share.
CREATE OR REPLACE VIEW jdub_demo.geologic.v_answer_share_weekly AS
WITH r AS (
  SELECT pr.*, runs.started_at FROM jdub_demo.geologic.probe_responses pr
  JOIN jdub_demo.geologic.probe_runs runs USING (run_id)
  JOIN jdub_demo.geologic.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch),
weeks AS (SELECT DISTINCT date_trunc('week', started_at)::date AS week_start FROM r),
snap AS (
  SELECT w.week_start, r.*,
         ROW_NUMBER() OVER (PARTITION BY w.week_start, r.prompt_id, r.engine ORDER BY r.started_at DESC) AS snap_rn
  FROM weeks w JOIN r ON r.started_at < date_add(w.week_start, 7)),
ok AS (
  SELECT s.* FROM snap s JOIN jdub_demo.geologic.v_prompts p ON p.prompt_id = s.prompt_id
  WHERE s.snap_rn = 1 AND s.status = 'ok' AND NOT p.branded)
SELECT week_start, brand, answer_share FROM jdub_demo.geologic.answer_share_weekly
UNION ALL
SELECT week_start, 'Little Caesars' AS brand,
       AVG(CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END) AS answer_share
FROM ok GROUP BY week_start
UNION ALL
SELECT week_start, concat('Domino', chr(39), 's') AS brand,
       AVG(COALESCE(1.0 / NULLIF(array_position(brands_mentioned, concat('Domino', chr(39), 's')), 0), 0)) AS answer_share
FROM ok GROUP BY week_start;
