#!/usr/bin/env bash
# Build, bundle-deploy and start GEOlogic on the DEFAULT profile for one bundle target.
# Usage: TARGET=v3 [SKIP_BUILD=1] bash scripts/deploy.sh   (SKIP_BUILD=1 reuses the existing app/frontend/dist)
# Optional overrides: WAREHOUSE_ID, LAKEBASE_HOST, GENIE_SPACE_ID (passed as --var).
set -euo pipefail
cd "$(dirname "$0")/.."
# Target checks come first: nothing below (databricks, npm, rsync) may run for a missing or v2 target.
if [ -z "${TARGET:-}" ]; then
  echo "Set TARGET, for example: TARGET=v3 bash scripts/deploy.sh"; exit 1
fi
if [ "$TARGET" = "dev" ] && [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)" = "build/v3" ]; then
  echo "Refusing TARGET=dev on branch build/v3, even with ALLOW_V2_DEPLOY=1: this branch's dev config no longer matches live v2."; exit 1
fi
if [ "$TARGET" = "dev" ] && [ "${ALLOW_V2_DEPLOY:-0}" != "1" ]; then
  echo "Refusing TARGET=dev: it is the live v2 demo. Deploy v2 only from the v2 branch with ALLOW_V2_DEPLOY=1."; exit 1
fi
PROFILE=DEFAULT
VARS=()
[ -n "${WAREHOUSE_ID:-}" ] && VARS+=(--var "warehouse_id=$WAREHOUSE_ID")
[ -n "${LAKEBASE_HOST:-}" ] && VARS+=(--var "lakebase_host=$LAKEBASE_HOST")
[ -n "${GENIE_SPACE_ID:-}" ] && VARS+=(--var "genie_space_id=$GENIE_SPACE_ID")
BUNDLE=(-t "$TARGET" "${VARS[@]+"${VARS[@]}"}" --profile "$PROFILE")

# 0. Resolve the target and refuse it if it names any resource of another stack (scripts/check_plan.py
#    --summary), or if its bundle state records a different app name (a forced app replace).
SUMMARY=$(mktemp)
trap 'rm -f "$SUMMARY"' EXIT
databricks bundle summary -o json "${BUNDLE[@]}" > "$SUMMARY"
APP_NAME=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['resources']['apps']['geologic']['name'])" "$SUMMARY")
python3 scripts/check_plan.py --summary "$SUMMARY" --target "$TARGET" --state-dir ".databricks/bundle/$TARGET"

# Guard (memory: bundle_deploy_forces_app_replace). Whether the live app exists is checked again
# against the plan in step 3 (scripts/check_plan.py refuses `create` of adopted resources), because
# .databricks/bundle state also appears after a plain validate/plan without any bind.
APP_EXISTS=0
databricks apps get "$APP_NAME" --profile "$PROFILE" >/dev/null 2>&1 && APP_EXISTS=1
if [ "$APP_EXISTS" = "1" ] && [ ! -d ".databricks/bundle/$TARGET" ]; then
  echo "App '$APP_NAME' exists but this checkout has no bundle state for target $TARGET. Bind it (see README) before deploying."; exit 1
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
databricks bundle validate --strict "${BUNDLE[@]}"
PLAN=$(mktemp)
databricks bundle plan -o json "${BUNDLE[@]}" > "$PLAN"
python3 scripts/check_plan.py "$PLAN" --target "$TARGET" $([ "$APP_EXISTS" = "1" ] && echo --app-exists) || { rm -f "$PLAN"; exit 1; }
rm -f "$PLAN"

# 4. Deploy (uploads files, updates jobs, pipeline, dashboard and the app object).
databricks bundle deploy "${BUNDLE[@]}"

# 5. Confirm the built frontend landed (memory: apps_dist_sync). sync.include covers the
#    gitignored dist; fall back to an explicit import if the hashes differ.
APP_PATH=$(databricks bundle summary -o json "${BUNDLE[@]}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['resources']['apps']['geologic']['source_code_path'])")
LOCAL_JS=$(ls app/frontend/dist/assets | grep -E '^index-.*\.js$' | sort)
REMOTE_JS=$(databricks workspace list "$APP_PATH/frontend/dist/assets" --profile "$PROFILE" -o json \
  | python3 -c "import json,sys,os;print('\n'.join(sorted(os.path.basename(o['path']) for o in json.load(sys.stdin) if os.path.basename(o['path']).startswith('index-') and o['path'].endswith('.js'))))" || true)
if [ "$LOCAL_JS" != "$REMOTE_JS" ]; then
  echo "dist mismatch (local: $LOCAL_JS, remote: $REMOTE_JS); importing dist explicitly"
  databricks workspace import-dir app/frontend/dist "$APP_PATH/frontend/dist" --overwrite --profile "$PROFILE"
fi

# 6. Deploy the app snapshot with the bundle's config.env (a bare `apps deploy` would skip it).
databricks bundle run geologic "${BUNDLE[@]}"
databricks apps get "$APP_NAME" --profile "$PROFILE" -o json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('url'), d.get('app_status', {}).get('state'), ((d.get('active_deployment') or {}).get('status') or {}).get('state'))"
