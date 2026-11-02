-- GEOlogic probe traffic as recorded by AI Gateway usage tracking. Probes tag requests with
-- usage_context app=geologic (src/geologic/probe/engine.py), so shared endpoints' other traffic is excluded.
-- served_entities has a row per entity version: dedupe it so each request counts once.
-- Owned by the deployer (needs SELECT on system.serving); the app SP reads the view through its schema grant.
CREATE OR REPLACE VIEW jdub_demo.geologic.v_gateway_usage AS
SELECT se.endpoint_name, count(*) AS requests, max(u.request_time) AS last_request
FROM system.serving.endpoint_usage u
JOIN (SELECT DISTINCT served_entity_id, endpoint_name FROM system.serving.served_entities) se USING (served_entity_id)
WHERE u.usage_context['app'] = 'geologic'
GROUP BY se.endpoint_name;
