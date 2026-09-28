CREATE OR REPLACE VIEW jdub_demo.geologic.v_prompts AS
SELECT prompt_id, prompt_text, cluster, base_volume, true AS tracked FROM jdub_demo.geologic.prompt_bank
UNION ALL
SELECT c.prompt_id, c.prompt_text, c.cluster, c.base_volume, t.prompt_id IS NOT NULL AS tracked
FROM jdub_demo.geologic.prompt_candidates c
LEFT JOIN (SELECT DISTINCT prompt_id FROM jdub_demo.geologic.tracked_prompts) t USING (prompt_id);

CREATE OR REPLACE VIEW jdub_demo.geologic.v_prompt_status AS
WITH r AS (SELECT * FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok'),
v AS (SELECT prompt_id, avg(est_volume) AS avg_monthly_volume FROM jdub_demo.geologic.question_volume_monthly GROUP BY prompt_id)
SELECT p.prompt_id, p.prompt_text, p.cluster, p.tracked, round(v.avg_monthly_volume) AS avg_monthly_volume,
       CASE WHEN v.avg_monthly_volume >= 8000 THEN 'High' WHEN v.avg_monthly_volume >= 3000 THEN 'Medium' ELSE 'Low' END AS volume_tier,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       SUM(CASE WHEN r.lce_mentioned THEN 1 ELSE 0 END) AS engines_naming,
       COUNT(r.engine) AS engines_answered,
       MAX(size(filter(r.claims, x -> x.verdict = 'wrong'))) > 0 AS has_wrong_claim,
       (SELECT min(started_at) FROM jdub_demo.geologic.probe_runs pr WHERE array_contains(pr.prompt_ids, p.prompt_id)) AS first_tracked,
       (SELECT max(finished_at) FROM jdub_demo.geologic.probe_runs pr WHERE array_contains(pr.prompt_ids, p.prompt_id)) AS updated_at
FROM jdub_demo.geologic.v_prompts p LEFT JOIN v USING (prompt_id) LEFT JOIN r USING (prompt_id)
GROUP BY p.prompt_id, p.prompt_text, p.cluster, p.tracked, v.avg_monthly_volume;

CREATE OR REPLACE VIEW jdub_demo.geologic.v_theme_sentiment AS
SELECT theme, count(*) AS answers,
       avg(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS pct_positive,
       avg(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS pct_negative,
       min_by(substr(answer, 1, 90), CASE WHEN sentiment = 'negative' THEN 0 ELSE 1 END * 1000 + length(answer)) AS sample_quote
FROM jdub_demo.geologic.answer_themes GROUP BY theme;

CREATE OR REPLACE VIEW jdub_demo.geologic.v_leaderboard AS
WITH cites AS (SELECT explode(cited_doc_ids) AS doc_id FROM jdub_demo.geologic.v_latest_responses WHERE status = 'ok'),
by_brand AS (SELECT b.brand, count(*) AS n FROM cites JOIN jdub_demo.geologic.doc_brand b USING (doc_id) GROUP BY b.brand),
total AS (SELECT count(*) AS n FROM cites)
SELECT s.brand, s.answer_share, coalesce(bb.n / t.n, 0) AS citation_share
FROM jdub_demo.geologic.v_brand_share s LEFT JOIN by_brand bb USING (brand) CROSS JOIN total t;
