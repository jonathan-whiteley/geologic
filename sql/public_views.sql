CREATE OR REPLACE VIEW jdub_demo.geologic.v_public_signals AS
SELECT signal_id, source_type, ingested_at, author, reach, velocity, text, page, hits, image_uri,
       topic, sentiment, menu_item_id, persona_id, image_match_score, resolution_confidence
FROM jdub_demo.geologic.silver_signals WHERE NOT quarantined;
