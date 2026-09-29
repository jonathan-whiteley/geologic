-- Lakeflow SDP. Pipeline default catalog jdub_demo, schema geologic.
-- Deviation from brief (1): ai_classify returns VARIANT {response:[label], error_message};
--   extracted with :response[0]::STRING so topic is a STRING column.
-- Deviation from brief (2): labels passed as JSON string literal (documented API),
--   not ARRAY(...) which produces a SQL ARRAY type and may error.
-- Deviation from brief (3): lower() on both sides of persona and topic/category
--   comparisons to match exclusions.py semantics (ref = object_ref.lower(),
--   persona_id.lower() == ref, topic_set uses t.lower()).
-- Semantic note: SQL uses min(rule_id) to pick one rule per signal; Python iterates
--   rules in insertion order and returns the first match. For seeded data the results
--   agree because rule_ids are in alphabetical == insertion order (EX-01 < EX-07).

CREATE OR REFRESH STREAMING TABLE silver_signals_raw AS
SELECT signal_id, source_type, timestamp_micros(ingested_at) AS ingested_at, image_uri,
       p.author, p.author_persona_id, p.reach, p.velocity, p.text, p.bot, p.page, p.hits,
       ai_classify(p.text, '["menu_item","deal","game_day","complaint","politics","gambling","arrest","crawler"]'):response[0]::STRING AS topic,
       ai_analyze_sentiment(p.text) AS sentiment
FROM (SELECT *, from_json(payload, 'author STRING, author_persona_id STRING, reach BIGINT, velocity DOUBLE, text STRING, bot STRING, page STRING, hits INT') AS p
      FROM STREAM(bronze_signals));

CREATE OR REFRESH MATERIALIZED VIEW silver_signals AS
WITH aliases AS (
  SELECT item_id, lower(trim(a)) AS alias
  FROM menu_items LATERAL VIEW explode(array_union(aliases, array(lower(name)))) t AS a
  WHERE length(trim(a)) >= 4
),
text_match AS (
  SELECT s.signal_id, max_by(a.item_id, length(a.alias)) AS item_id
  FROM silver_signals_raw s JOIN aliases a ON lower(s.text) LIKE concat('%', a.alias, '%')
  GROUP BY s.signal_id
),
excl AS (
  SELECT s.signal_id, min(r.rule_id) AS rule_id
  FROM silver_signals_raw s JOIN exclusion_rules r
    ON r.active AND (
      (r.object_type = 'persona' AND lower(s.author_persona_id) = lower(r.object_ref)) OR
      (r.object_type IN ('topic', 'category') AND (lower(s.topic) = lower(r.object_ref) OR lower(s.text) LIKE concat('%', lower(r.object_ref), '%'))))
  GROUP BY s.signal_id
)
SELECT s.*,
       coalesce(tm.item_id, CASE WHEN i.match_score >= 0.6 THEN i.matched_item_id END) AS menu_item_id,
       per.persona_id, coalesce(per.is_real, false) AS is_real_persona,
       i.description AS image_description, i.match_score AS image_match_score,
       CASE WHEN tm.item_id IS NOT NULL THEN 0.95 WHEN i.match_score IS NOT NULL THEN i.match_score ELSE 0.0 END AS resolution_confidence,
       e.rule_id IS NOT NULL AS quarantined, e.rule_id AS quarantine_rule_id
FROM silver_signals_raw s
LEFT JOIN text_match tm USING (signal_id)
LEFT JOIN image_descriptions i USING (signal_id)
LEFT JOIN personas per ON per.persona_id = s.author_persona_id
LEFT JOIN excl e USING (signal_id);
