# GEOlogic

Generative Engine Optimization demo for Little Caesars on Databricks. GEOlogic probes AI answer
engines with a prompt bank, measures **Answer Share** (rank-weighted mention rate), finds wrong
claims and content gaps, drafts fixes, and publishes approved content through a governed flow.

Everything deploys as one Declarative Automation Bundle (`databricks.yml` plus `resources/*.yml`)
to the `DEFAULT` CLI profile (`fe-vm-jdub-vm-serverless`), catalog `jdub_demo`, schema `geologic`.

## What the bundle manages

| Key | Type | Live name |
|---|---|---|
| `geologic` | App | `geologic` |
| `geologic_signals` | Pipeline | `geologic-signals` |
| `geologic_impact` | Dashboard | `GEOlogic Impact` |
| `geologic_setup` | Job | `geologic_setup` (full first-time build) |
| `geologic_publish` | Job | `geologic_publish` (param `suggestion_id`) |
| `geologic_reset` | Job | `geologic_reset` |
| `geologic_produce` | Job | `geologic_produce` (params `inject`, `minutes`, `rate_per_min`) |
| `geologic_refresh` | Job | `geologic_refresh` (every minute, created PAUSED) |
| `geologic_deploy_strategist` | Job | one-off: deploy the content strategist agent |
| `geologic_verify_uc` | Job | one-off: verify the UC functions |

Not bundle managed (provisioned once, out of band): the Lakebase instance `geologic`, the serving
endpoints (`geologic-content-strategist` is deployed by the `geologic_deploy_strategist` job; the
Supervisor agent endpoint is created in Agent Bricks), the Genie space, and the Zerobus service
principal and secret scope. The Vector Search endpoint and indexes are created by the
`geologic_setup` job (`jobs/setup_vector_search.py`).

## Prerequisites

- Databricks CLI v1.x authenticated: `databricks auth login --profile DEFAULT`
- Node 18+ and npm (the frontend is built locally; only `app/frontend/dist` ships). `npm ci` is
  pinned to a lockfile that resolves through the Databricks npm proxy, so be on that registry/VPN.
- `python3` and `rsync` (used by `scripts/deploy.sh`)
- Test env: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev,databricks]'`, then
  `.venv/bin/python -m pytest -q` (or `uv sync` using the committed `uv.lock`)
- A serverless SQL warehouse id (bundle variable `warehouse_id`)
- Lakebase instance `geologic` and its host (`read_write_dns`, bundle variable `lakebase_host`)
- Zerobus ingest secrets for `geologic_produce`
- Supervisor agent endpoint name (bundle variable `supervisor_endpoint`)

Bundle variable defaults in `databricks.yml` hold the live values for this workspace. Override any
of them with `WAREHOUSE_ID`, `LAKEBASE_HOST`, `APP_SP_CLIENT_ID` or `SUPERVISOR_ENDPOINT` when running
`scripts/deploy.sh`.

## Deploy

```bash
bash scripts/deploy.sh             # build frontend, bundle src, validate, plan, deploy, start app
SKIP_BUILD=1 bash scripts/deploy.sh  # reuse the existing app/frontend/dist
```

The script:

1. Builds the frontend (`npm ci && npm run build`).
2. Copies `src/geologic` into `app/src` (the app imports the bundled copy).
3. Runs `bundle validate --strict` and `bundle plan`, and refuses to deploy (`scripts/check_plan.py`)
   if the plan is empty, deletes or recreates anything, or (when the live app exists) would create
   one of the adopted resources, which means the checkout is not bound yet.
4. Runs `bundle deploy`, then checks that the built `dist` assets landed in the app source path
   (imports them explicitly if not).
5. Runs `bundle run geologic`, which deploys the app snapshot with the env from
   `resources/app.yml` `config.env`. A bare `databricks apps deploy` skips that env.

Sync notes: `app/src` and `app/frontend/dist` are gitignored, so `databricks.yml` lists them under
`sync.include`. Frontend sources, `package.json` and `node_modules` are excluded so the Apps
runtime never tries an npm build.

## First-time setup in a fresh workspace

Do these in order.

1. **Lakebase.** Create the Lakebase instance `geologic` and apply `sql/lakebase_schema.sql` to its
   `geologic` database. Note its `read_write_dns`.
2. **Zerobus.** Create a service principal for Zerobus ingest, grant it access to
   `jdub_demo.geologic.bronze_signals`, and store `zb_endpoint`, `zb_client_id` and
   `zb_client_secret` in the secret scope `geologic` (read by `src/geologic/producer.py`).
3. **Point the code at the new workspace.** Jobs do not receive bundle variables, they read code
   defaults:
   - `src/geologic/lakebase.py` `LAKEBASE_DEFAULTS` (host, db, instance)
   - `src/geologic/config.py` `catalog` and `schema`
   The bundle variables (`catalog`, `schema`, `warehouse_id`, `lakebase_host`, `app_sp_client_id`,
   `supervisor_endpoint`) only reach the app, pipeline and dashboard. Also: the dashboard JSON
   hard-codes `jdub_demo.geologic`, the `sql/*.sql` files and `jobs/run_views.py` hard-code the
   same names, and `resources/dashboard.yml` `parent_path` is a personal workspace folder; change it.
4. `bash scripts/deploy.sh`. A new app gets a new service principal; read it with
   `databricks apps get geologic --profile DEFAULT -o json` (`service_principal_client_id`), set
   `app_sp_client_id` (or `APP_SP_CLIENT_ID`), then redeploy.
5. **Grants for the app SP:**
   - Lakebase: `CAN_USE` on the instance; create the SP Postgres role, then grant `USAGE` on the
     schema, `SELECT, INSERT, UPDATE, DELETE` on its tables and `USAGE, SELECT` on its sequences.
   - UC: `USE CATALOG` on `jdub_demo`; `USE SCHEMA, SELECT, EXECUTE` on `jdub_demo.geologic`;
     `READ VOLUME` on `jdub_demo.geologic.assets`; `MODIFY` on `jdub_demo.geologic.tracked_prompts`;
     `SELECT` on `jdub_demo.geologic.prompt_idx`.
   - `CAN_USE` on the SQL warehouse.
   - Genie space ACL `CAN_RUN` and Supervisor endpoint `CAN_QUERY` (applied in step 9, after they exist).
6. `databricks bundle run geologic_setup --profile DEFAULT` (about 30 to 40 minutes). It generates
   the reference data, images, corpus, Vector Search indexes, the baseline probe, the SQL views
   (`views` task, `jobs/run_views.py`), themes, opportunities and the draft queue.
7. **SQL objects** (run with the warehouse): `sql/uc_functions.sql`, `sql/supervisor_tools.sql`,
   `sql/metric_views.sql`. Metric-view YAML must go through
   `databricks api post /api/2.0/sql/statements` (statement text in the JSON body); the CLI
   statement helpers strip the indentation and break the YAML.
8. `databricks bundle run geologic_deploy_strategist --profile DEFAULT` (serves
   `geologic-content-strategist`; `supervisor_tools.sql` depends on it at call time).
9. **Genie and Supervisor.** Create the Genie space from `genie/space.json`, then the Supervisor
   per `docs/supervisor.md`. Grant the app SP `CAN_RUN` on the Genie space, set the `supervisor_endpoint`
   variable (or `SUPERVISOR_ENDPOINT=... bash scripts/deploy.sh`) and redeploy; the bundle binds the
   endpoint to the app with `CAN_QUERY`.

Note: S1/S2 improve-after-publish checks in the answer-key test only run when `accuracy_by_run` /
`share_by_run` are supplied.

## Adopting existing resources (no recreate)

If the app, pipeline, dashboard or jobs already exist (created outside the bundle), bind them
before the first deploy so the bundle updates them in place:

```bash
databricks bundle deployment bind geologic geologic --profile DEFAULT
databricks bundle deployment bind geologic_signals <pipeline_id> --profile DEFAULT
databricks bundle deployment bind geologic_impact <dashboard_id> --profile DEFAULT
databricks bundle deployment bind geologic_publish <job_id> --profile DEFAULT
databricks bundle deployment bind geologic_reset <job_id> --profile DEFAULT
databricks bundle deployment bind geologic_produce <job_id> --profile DEFAULT
```

Keep resource names identical to the live names (the target has no `mode: development` for this
reason) and the dashboard `parent_path` equal to its live folder. Always read `bundle plan` first.

## Demo-day checklist

1. Click **Reset** in the app to return to the baseline.
2. Run the demo (see `docs/`). The rehearsed path keeps `geologic_refresh` paused.
3. OPTIONAL, only if showing the live Signals stream: unpause `geologic_refresh` (Jobs UI, or set
   `pause_status: UNPAUSED` and redeploy) and stream background signals with
   `databricks bundle run geologic_produce --params minutes=15 --profile DEFAULT`.
   Warning: refresh rebuilds `gold_opportunities` every minute, so Prioritize ranks can reshuffle,
   Reset does not restore `gold_opportunities`, and the next `scripts/deploy.sh` re-pauses refresh.
4. If you unpaused refresh, pause it again afterwards.

Re-drafting (`geologic_setup` `draft` task, `jobs/draft_suggestions.py`): only do it from a freshly
Reset state. A T0 row already live is not re-applied, and if any draft fails the job exits non-zero
without writing the Reset baseline tables, so a partial queue never becomes the baseline.

## Teardown

`databricks bundle destroy --profile DEFAULT` deletes everything the bundle manages, including the
adopted app and jobs. Only run it when the demo is retired. Then delete by hand: the Vector Search
endpoint, the Lakebase instance, the serving endpoints, the Genie space, the Supervisor, the Zerobus
service principal and secret scope `geologic`, the UC schema `jdub_demo.geologic`, and the MLflow
experiment `/Shared/geologic-drafting`. A recreated app gets a new service principal: re-grant
everything in step 5 of first-time setup.

## Tests

```bash
.venv/bin/python -m pytest -q
```
