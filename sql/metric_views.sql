CREATE OR REPLACE VIEW {{schema}}.mv_answer_share
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
source: SELECT r.*, p.cluster, p.prompt_text, p.branded, coalesce(c.correct, 0) AS correct_claims, coalesce(c.bad, 0) AS bad_claims FROM {{schema}}.v_latest_responses r JOIN {{schema}}.v_prompts p USING (prompt_id) LEFT JOIN (SELECT answer_id, count_if(tag = 'Correct') AS correct, count_if(tag IN ('Wrong', 'Outdated')) AS bad FROM {{schema}}.claims GROUP BY answer_id) c USING (answer_id) WHERE r.status = 'ok'
dimensions:
  - name: Cluster
    expr: cluster
  - name: Engine
    expr: engine
measures:
  - name: Share of Model
    expr: AVG(CASE WHEN NOT branded THEN CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END END)
    comment: "Unbranded prompts only, like v_kpis. Citation Rate and Fact Accuracy use all prompts."
  - name: Citation Rate
    expr: AVG(CASE WHEN cites_official THEN 1 ELSE 0 END)
  - name: Fact Accuracy
    expr: SUM(correct_claims) / NULLIF(SUM(correct_claims + bad_claims), 0)
    comment: "Correct over Correct, Wrong and Outdated claims, tagged against brand_facts."
  - name: Answers
    expr: COUNT(1)
$$;
