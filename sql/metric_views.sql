CREATE OR REPLACE VIEW jdub_demo.geologic.mv_answer_share
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
source: SELECT r.*, p.cluster, p.prompt_text FROM jdub_demo.geologic.v_latest_responses r JOIN jdub_demo.geologic.v_prompts p USING (prompt_id) WHERE r.status = 'ok' AND NOT p.branded
dimensions:
  - name: Cluster
    expr: cluster
  - name: Engine
    expr: engine
measures:
  - name: Answer Share
    expr: AVG(CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END)
  - name: Citation Rate
    expr: AVG(CASE WHEN cites_official THEN 1 ELSE 0 END)
  - name: Fact Accuracy
    expr: SUM(size(filter(claims, c -> c.verdict = 'correct'))) / NULLIF(SUM(size(filter(claims, c -> c.verdict IN ('correct','wrong')))), 0)
  - name: Answers
    expr: COUNT(1)
$$;
