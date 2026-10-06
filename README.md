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
endpoints (`geologic-content-strategist`, the Supervisor agent endpoint), the Genie space, the
Vector Search endpoint and indexes, and the Zerobus secrets.

## Prerequisites

- Databricks CLI v1.x authenticated: `databricks auth login --profile DEFAULT`
- Node 18+ and npm (the frontend is built locally; only `app/frontend/dist` ships)
- A serverless SQL warehouse id (bundle variable `warehouse_id`)
- Lakebase instance `geologic` and its host (`read_write_dns`, bundle variable `lakebase_host`)
- Zerobus ingest secrets for `geologic_produce`
- Supervisor agent endpoint name (bundle variable `supervisor_endpoint`)

Bundle variable defaults in `databricks.yml` hold the live values for this workspace. Override any
of them with `WAREHOUSE_ID`, `LAKEBASE_HOST` or `APP_SP_CLIENT_ID` when running `scripts/deploy.sh`.

## Deploy

```bash
bash scripts/deploy.sh             # build frontend, bundle src, validate, plan, deploy, start app
SKIP_BUILD=1 bash scripts/deploy.sh  # reuse the existing app/frontend/dist
```

The script:

1. Builds the frontend (`npm ci && npm run build`).
2. Copies `src/geologic` into `app/src` (the app imports the bundled copy).
3. Runs `bundle validate --strict` and `bundle plan`, and refuses to deploy if the plan deletes or
   recreates anything.
4. Runs `bundle deploy`, then checks that the built `dist` assets landed in the app source path
   (imports them explicitly if not).
5. Runs `bundle run geologic`, which deploys the app snapshot with the env from
   `resources/app.yml` `config.env`. A bare `databricks apps deploy` skips that env.

Sync notes: `app/src` and `app/frontend/dist` are gitignored, so `databricks.yml` lists them under
`sync.include`. Frontend sources, `package.json` and `node_modules` are excluded so the Apps
runtime never tries an npm build.

## First-time setup in a fresh workspace

1. One-offs: Lakebase instance and schema, serving endpoints, Genie space, Zerobus secrets.
2. `bash scripts/deploy.sh`. A new app gets a new service principal; read it with
   `databricks apps get geologic --profile DEFAULT -o json` (`service_principal_client_id`) and
   set `app_sp_client_id` (or `APP_SP_CLIENT_ID`), then redeploy.
3. Grants for the app SP:
   - UC: `USE CATALOG` on `jdub_demo`; `USE SCHEMA, SELECT, EXECUTE` on `jdub_demo.geologic`;
     `READ VOLUME` on `jdub_demo.geologic.assets`; `MODIFY` on `jdub_demo.geologic.tracked_prompts`;
     `SELECT` on `jdub_demo.geologic.prompt_idx`.
   - Genie space ACL: `CAN_RUN` (a Genie space is not a bindable app resource).
   - Lakebase: create the SP Postgres role, then grant `USAGE` on the schema and
     `SELECT, INSERT, UPDATE, DELETE` on its tables and `USAGE, SELECT` on its sequences.
4. `databricks bundle run geologic_setup --profile DEFAULT` (about 30 to 40 minutes; regenerates
   the reference data, corpus, indexes and the baseline probe).

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

1. Unpause `geologic_refresh` (Jobs UI, or edit `pause_status` and redeploy).
2. Run `geologic_produce` with `minutes=15` to stream background signals.
3. Click **Reset** in the app to return to the baseline.
4. Run the demo (see `docs/`).
5. Pause `geologic_refresh` again.

## Teardown

`databricks bundle destroy --profile DEFAULT` deletes everything the bundle manages, including the
adopted app and jobs. Only run it when the demo is retired. Then delete the Vector Search endpoint,
the Lakebase instance and the serving endpoints by hand.

## Tests

```bash
.venv/bin/python -m pytest -q
```
