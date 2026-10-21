CREATE OR REPLACE FUNCTION {{schema}}.check_exclusions(text STRING, persona_id STRING)
RETURNS STRING
COMMENT 'Returns the exclusion rule_id this text or persona violates, or NULL. Brand Guardian tool.'
RETURN (
  SELECT min(rule_id) FROM {{schema}}.exclusion_rules r
  WHERE r.active AND ((r.object_type = 'persona' AND r.object_ref = check_exclusions.persona_id)
     OR (r.object_type IN ('topic', 'category') AND lower(check_exclusions.text) LIKE concat('%', r.object_ref, '%')))
);

CREATE OR REPLACE FUNCTION {{schema}}.assign_tier(asset_type STRING, names_person BOOLEAN, checks_ok BOOLEAN)
RETURNS STRING
COMMENT 'Deterministic autonomy tier. Mirrors geologic.tiering.assign_tier.'
RETURN CASE
  WHEN names_person OR asset_type IN ('association', 'correction_email', 'community_reply') THEN 'T2'
  WHEN asset_type = 'jsonld' THEN CASE WHEN checks_ok THEN 'T0' ELSE 'T1' END
  WHEN asset_type IN ('owned_patch', 'answer_page', 'moment_page') THEN 'T1'
  ELSE 'T2' END;

CREATE OR REPLACE FUNCTION {{schema}}.validate_jsonld(jsonld STRING)
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

CREATE OR REPLACE FUNCTION {{schema}}.check_facts(text STRING)
RETURNS STRING
COMMENT 'Returns a JSON array of dollar amounts in the text that match no current price fact in brand_facts.'
RETURN (
  SELECT to_json(collect_list(p)) FROM (
    SELECT DISTINCT CAST(regexp_replace(m, '[$ ]', '') AS DOUBLE) AS p
    FROM (SELECT explode(regexp_extract_all(check_facts.text, '\\$\\s?[0-9]+(\\.[0-9]{2})?', 0)) AS m)
  ) x WHERE p NOT IN (SELECT value_num FROM {{schema}}.brand_facts WHERE attribute = 'price'
                      AND valid_from <= current_date() AND (valid_to IS NULL OR valid_to >= current_date()))
);
