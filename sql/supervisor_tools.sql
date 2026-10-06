-- Wrapper so the Agent Bricks Supervisor can call the Content Strategist serving endpoint
-- (the Supervisor tool API has no serving-endpoint tool type). opp and page are JSON object strings.
CREATE OR REPLACE FUNCTION jdub_demo.geologic.draft_page_change(opp STRING, page STRING)
RETURN get_json_object(
  ai_query('geologic-content-strategist',
    request => concat('{"opp":', opp, ',"page":', page, '}'),
    failOnError => false).result,
  '$');
