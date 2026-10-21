-- Per-prompt status for Measure and the leaderboard. Owned doc ids always start with lce_ (pinned in the Task 2
-- tests), so startswith(x, 'lce_') is the owned test inside the cited and retrieved arrays.
CREATE OR REPLACE VIEW {{schema}}.v_prompt_status AS
WITH r AS (SELECT * FROM {{schema}}.v_latest_responses WHERE status = 'ok'),
cl AS (
  SELECT prompt_id, SUM(CASE WHEN tag = 'Wrong' THEN 1 ELSE 0 END) AS wrong_claims,
         SUM(CASE WHEN tag = 'Outdated' THEN 1 ELSE 0 END) AS outdated_claims
  FROM {{schema}}.v_latest_claims GROUP BY prompt_id),
vol AS (SELECT prompt_id, avg(est_volume) AS est_monthly_searches FROM {{schema}}.question_volume_monthly GROUP BY prompt_id),
mom AS (
  SELECT pid AS prompt_id, max_by(moment_id, reach) AS moment_id, max_by(title, reach) AS moment_title
  FROM {{schema}}.moments LATERAL VIEW explode(prompt_ids) t AS pid GROUP BY pid)
SELECT p.prompt_id, p.prompt_text, p.cluster, p.priority, p.branded, round(vol.est_monthly_searches) AS est_monthly_searches,
       SUM(CASE WHEN r.lce_mentioned THEN 1 ELSE 0 END) AS engines_naming,
       SUM(CASE WHEN exists(r.cited_doc_ids, x -> startswith(x, 'lce_')) THEN 1 ELSE 0 END) AS engines_owned_cited,
       SUM(CASE WHEN exists(r.retrieved_doc_ids, x -> startswith(x, 'lce_')) THEN 1 ELSE 0 END) AS engines_owned_retrieved,
       COUNT(r.engine) AS engines_answered,
       AVG(CASE WHEN r.lce_mentioned AND r.lce_rank > 0 THEN 1.0 / r.lce_rank ELSE 0 END) AS answer_share,
       coalesce(max(cl.wrong_claims), 0) AS wrong_claims, coalesce(max(cl.outdated_claims), 0) AS outdated_claims,
       max(mom.moment_id) AS moment_id, max(mom.moment_title) AS moment_title
FROM {{schema}}.v_prompts p
LEFT JOIN r USING (prompt_id) LEFT JOIN cl USING (prompt_id) LEFT JOIN vol USING (prompt_id) LEFT JOIN mom USING (prompt_id)
GROUP BY p.prompt_id, p.prompt_text, p.cluster, p.priority, p.branded, vol.est_monthly_searches;

CREATE OR REPLACE VIEW {{schema}}.v_leaderboard AS
WITH cites AS (SELECT explode(cited_doc_ids) AS doc_id FROM {{schema}}.v_latest_responses WHERE status = 'ok'),
by_brand AS (SELECT b.brand, count(*) AS n FROM cites JOIN {{schema}}.doc_brand b USING (doc_id) GROUP BY b.brand),
total AS (SELECT count(*) AS n FROM cites)
SELECT s.brand, s.answer_share, s.avg_position, coalesce(bb.n / t.n, 0) AS citation_share
FROM {{schema}}.v_brand_share s LEFT JOIN by_brand bb USING (brand) CROSS JOIN total t;
