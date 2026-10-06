CREATE OR REPLACE VIEW jdub_demo.geologic.v_public_signals AS
SELECT signal_id, source_type, ingested_at, author, reach, velocity, text, page, hits, image_uri,
       topic, sentiment, menu_item_id, persona_id, image_match_score, resolution_confidence
FROM jdub_demo.geologic.silver_signals WHERE NOT quarantined;

CREATE OR REPLACE VIEW jdub_demo.geologic.v_answer_share_weekly AS
SELECT week_start, brand, answer_share FROM jdub_demo.geologic.answer_share_weekly
UNION ALL
SELECT date_trunc('week', runs.started_at)::date AS week_start, b.brand,
       AVG(COALESCE(1.0 / NULLIF(array_position(pr.brands_mentioned, b.brand), 0), 0)) AS answer_share
FROM jdub_demo.geologic.probe_responses pr
JOIN jdub_demo.geologic.probe_runs runs USING (run_id)
JOIN jdub_demo.geologic.probe_state st ON st.id = 1 AND pr.epoch = st.current_epoch
CROSS JOIN (SELECT explode(array('Little Caesars', concat('Domino', chr(39), 's'))) AS brand) b
WHERE pr.status = 'ok'
GROUP BY 1, 2;
