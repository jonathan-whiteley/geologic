CREATE OR REPLACE FUNCTION jdub_demo.geologic.check_exclusions(text STRING, persona_id STRING)
RETURNS STRING
COMMENT 'Returns the exclusion rule_id this text or persona violates, or NULL. Brand Guardian tool.'
RETURN (
  SELECT min(rule_id) FROM jdub_demo.geologic.exclusion_rules r
  WHERE r.active AND ((r.object_type = 'persona' AND r.object_ref = check_exclusions.persona_id)
     OR (r.object_type IN ('topic', 'category') AND lower(check_exclusions.text) LIKE concat('%', r.object_ref, '%')))
);

CREATE OR REPLACE FUNCTION jdub_demo.geologic.assign_tier(asset_type STRING, touches_persona BOOLEAN, visual_sourced BOOLEAN,
  exclusion_hit BOOLEAN, jsonld_valid BOOLEAN, resolution_confidence DOUBLE)
RETURNS STRING
COMMENT 'Deterministic autonomy tier. Mirrors geologic.tiering.assign_tier.'
RETURN CASE
  WHEN exclusion_hit THEN 'BLOCKED'
  WHEN touches_persona OR visual_sourced THEN 'T2'
  WHEN asset_type IN ('jsonld', 'alt_text', 'facts') THEN CASE WHEN NOT jsonld_valid OR resolution_confidence < 0.7 THEN 'T1' ELSE 'T0' END
  WHEN asset_type IN ('faq', 'description') THEN 'T1'
  ELSE 'T2' END;

CREATE OR REPLACE FUNCTION jdub_demo.geologic.validate_jsonld(jsonld STRING)
RETURNS STRING
LANGUAGE PYTHON
COMMENT 'Returns a JSON array of schema.org errors for MenuItem, Offer, Organization, or FAQPage JSON-LD. Empty array means valid.'
AS $$
import json
try:
    o = json.loads(jsonld)
except Exception:
    return json.dumps(["invalid JSON"])
t = o.get("@type")
if t not in {"MenuItem", "Offer", "Organization", "FAQPage"}:
    return json.dumps([f"unsupported @type {t}"])
errs = []
off = o.get("offers") if t == "MenuItem" else None
if off and off.get("priceCurrency") != "USD":
    errs.append("priceCurrency must be USD")
if t == "FAQPage" and not o.get("mainEntity"):
    errs.append("FAQPage needs questions with accepted answers")
return json.dumps(errs)
$$;

CREATE OR REPLACE FUNCTION jdub_demo.geologic.check_facts(text STRING)
RETURNS STRING
COMMENT 'Returns a JSON array of dollar amounts in the text that match no menu price or active deal.'
RETURN (
  SELECT to_json(collect_list(p)) FROM (
    SELECT DISTINCT CAST(regexp_replace(m, '[$ ]', '') AS DOUBLE) AS p
    FROM (SELECT explode(regexp_extract_all(check_facts.text, '\\$\\s?[0-9]+(\\.[0-9]{2})?', 0)) AS m)
  ) x WHERE p NOT IN (SELECT price FROM jdub_demo.geologic.menu_items UNION SELECT price FROM jdub_demo.geologic.deals WHERE active)
);
