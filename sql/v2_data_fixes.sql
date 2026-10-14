-- GEOlogic v2 final fix wave: one-time data and view fixes for the live demo (jdub_demo.geologic).
-- Run by the ops step after deploying this branch with scripts/deploy.sh. Every statement is idempotent.
-- Part A runs on the SQL warehouse (Databricks SQL, profile DEFAULT). Part B runs on the Lakebase database (psql).
--
-- Part A, SQL warehouse
--
-- O1: opportunity rows built before the rename still say "Answer Share". The app already rewrites this at read time;
-- this makes Genie read the new name too.
UPDATE jdub_demo.geologic.gold_opportunities SET reasoning = replace(reasoning, 'Answer Share', 'Share of Model') WHERE reasoning LIKE '%Answer Share%';

-- O2: reasoning text names clusters by key ("in game_day_party across 84 answers"). Show the same human labels as the
-- UI (src/geologic/datagen/reference.py CLUSTER_LABELS). The builder writes labels from now on.
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in product across', ' in Product questions across'), ' in product with', ' in Product questions with')
WHERE instr(reasoning, ' in product ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in value across', ' in Value and deals across'), ' in value with', ' in Value and deals with')
WHERE instr(reasoning, ' in value ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in comparison across', ' in Comparisons across'), ' in comparison with', ' in Comparisons with')
WHERE instr(reasoning, ' in comparison ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in ordering across', ' in Ordering / Pizza Portal across'), ' in ordering with', ' in Ordering / Pizza Portal with')
WHERE instr(reasoning, ' in ordering ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in dietary across', ' in Dietary across'), ' in dietary with', ' in Dietary with')
WHERE instr(reasoning, ' in dietary ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in game_day_party across', ' in Game-day / party sizing across'), ' in game_day_party with', ' in Game-day / party sizing with')
WHERE instr(reasoning, ' in game_day_party ') > 0;
UPDATE jdub_demo.geologic.gold_opportunities
SET reasoning = replace(replace(reasoning, ' in sponsorship across', ' in Sponsorship (NFL) across'), ' in sponsorship with', ' in Sponsorship (NFL) with')
WHERE instr(reasoning, ' in sponsorship ') > 0;

-- S2: served_entities has one row per served entity version, so the old join counted each request once per version.
-- Mirrors sql/gateway_views.sql. Run as the deployer (needs SELECT on system.serving).
CREATE OR REPLACE VIEW jdub_demo.geologic.v_gateway_usage AS
SELECT se.endpoint_name, count(*) AS requests, max(u.request_time) AS last_request
FROM system.serving.endpoint_usage u
JOIN (SELECT DISTINCT served_entity_id, endpoint_name FROM system.serving.served_entities) se USING (served_entity_id)
WHERE u.usage_context['app'] = 'geologic'
GROUP BY se.endpoint_name;

--
-- Part B, Lakebase (Postgres)
--
-- P2: the proof card shows the question it compares. The app tolerates the column missing until this runs.
ALTER TABLE proof_results ADD COLUMN IF NOT EXISTS prompt_text TEXT;
