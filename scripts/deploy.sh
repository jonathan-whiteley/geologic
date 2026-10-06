#!/usr/bin/env bash
# Build, bundle-deploy and start GEOlogic on the DEFAULT profile.
# Usage: bash scripts/deploy.sh            (SKIP_BUILD=1 reuses the existing app/frontend/dist)
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE=DEFAULT
VARS=()
[ -n "${WAREHOUSE_ID:-}" ] && VARS+=(--var "warehouse_id=$WAREHOUSE_ID")
[ -n "${LAKEBASE_HOST:-}" ] && VARS+=(--var "lakebase_host=$LAKEBASE_HOST")
[ -n "${APP_SP_CLIENT_ID:-}" ] && VARS+=(--var "app_sp_client_id=$APP_SP_CLIENT_ID")

# Guard (memory: bundle_deploy_forces_app_replace). If the app already exists but this checkout
# has no bundle state, deploying would try to create a second app. Bind first:
#   databricks bundle deployment bind geologic geologic --profile DEFAULT
if databricks apps get geologic --profile "$PROFILE" >/dev/null 2>&1 && [ ! -d .databricks/bundle/dev ]; then
  echo "App 'geologic' exists but this checkout has no bundle state. Bind it (see README) before deploying."; exit 1
fi

# 1. Build the frontend (only dist ships; node_modules and package.json are excluded from sync).
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  ( cd app/frontend && npm ci && npm run build )
fi
[ -f app/frontend/dist/index.html ] || { echo "app/frontend/dist is missing; build the frontend first"; exit 1; }

# 2. Bundle the shared package into the app source path (app/main.py imports from app/src).
mkdir -p app/src
rsync -a --delete --exclude __pycache__ --exclude '*.egg-info' src/geologic/ app/src/geologic/

# 3. Validate, then refuse to deploy if the plan deletes or recreates anything.
databricks bundle validate --strict "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE"
PLAN=$(mktemp)
databricks bundle plan -o json "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE" > "$PLAN"
python3 - "$PLAN" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1])).get("plan", {})
bad = {k: v.get("action") for k, v in plan.items() if v.get("action") in ("delete", "recreate", "replace")}
for k, v in plan.items():
    print(f"  {v.get('action'):>8}  {k}")
if bad:
    print("Plan deletes or recreates resources; refusing to deploy:", bad); sys.exit(1)
PY
rm -f "$PLAN"

# 4. Deploy (uploads files, updates jobs, pipeline, dashboard and the app object).
databricks bundle deploy "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE"

# 5. Confirm the built frontend landed (memory: apps_dist_sync). sync.include covers the
#    gitignored dist; fall back to an explicit import if the hashes differ.
APP_PATH=$(databricks bundle summary -o json "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['resources']['apps']['geologic']['source_code_path'])")
LOCAL_JS=$(ls app/frontend/dist/assets | grep -E '^index-.*\.js$' | sort)
REMOTE_JS=$(databricks workspace list "$APP_PATH/frontend/dist/assets" --profile "$PROFILE" -o json \
  | python3 -c "import json,sys,os;print('\n'.join(sorted(os.path.basename(o['path']) for o in json.load(sys.stdin) if os.path.basename(o['path']).startswith('index-') and o['path'].endswith('.js'))))" || true)
if [ "$LOCAL_JS" != "$REMOTE_JS" ]; then
  echo "dist mismatch (local: $LOCAL_JS, remote: $REMOTE_JS); importing dist explicitly"
  databricks workspace import-dir app/frontend/dist "$APP_PATH/frontend/dist" --overwrite --profile "$PROFILE"
fi

# 6. Deploy the app snapshot with the bundle's config.env (a bare `apps deploy` would skip it).
databricks bundle run geologic "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE"
databricks apps get geologic --profile "$PROFILE" -o json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['url'], d['app_status']['state'], d['active_deployment']['status']['state'])"
