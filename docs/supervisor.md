# GEOlogic Supervisor

- Display name: `geologic-supervisor` (Agent Bricks Supervisor, id `supervisor-agents/044fdd7b-5124-4513-8f76-55309c436129`)
- Serving endpoint (set `GEOLOGIC_SUPERVISOR_ENDPOINT` to this): `mas-044fdd7b-endpoint`
  (Agent Bricks generates the endpoint name; it cannot be set to `geologic-supervisor`.)
- Query: `w.serving_endpoints.get_open_ai_client().responses.create(model="mas-044fdd7b-endpoint", input=[{"role":"user","content":q}])`, read `.output_text`.
- Grants: app service principal `bbbf2434-aa55-4e84-95ea-2679b7607d4c` has CAN_QUERY on the endpoint and CAN_RUN on the Genie space.

## Genie space

"GEOlogic Signal Analyst", `GENIE_SPACE_ID=01f1c1ad57691e9ab2457acf2bff7d78` (definition in `genie/space.json`).

## Subagents (tools)

1. `signal_analyst`: Genie space "GEOlogic Signal Analyst". "Answers data questions about Answer Share, engines, clusters, wrong claims, signals, and opportunities."
2. `content_strategist`: UC function `jdub_demo.geologic.draft_page_change(opp, page)` (see `sql/supervisor_tools.sql`), which calls serving endpoint `geologic-content-strategist` via `ai_query`. The Supervisor tool API has no serving-endpoint tool type, so the wrapper stands in. "Drafts a page change for an opportunity." opp and page are JSON object strings.
3. `guardian_check_exclusions`, `guardian_check_facts`, `guardian_validate_jsonld`: UC functions `jdub_demo.geologic.*`. "Brand Guardian checks. Run on any drafted copy before recommending it."

## Instructions

```
You are GEOlogic, a GEO copilot for the Little Caesars marketing team. Route data questions to the Signal Analyst.
Route drafting to the Content Strategist, then always run Brand Guardian checks on the draft and report results.
Keep answers under 120 words. Use plain language. Never mention people blocked by exclusion rules.
```
