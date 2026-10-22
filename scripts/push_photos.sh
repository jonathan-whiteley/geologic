#!/usr/bin/env bash
# Upload the credited photos (src/geologic/photos.py CREDITS) found locally in assets/photos/ to the target's assets
# volume. The Goff press photo is gitignored, so the bundle never carries it; without this step the images task draws
# a placeholder and the vision model sees no food. jobs/make_images.py never overwrites a file already in the volume.
# Usage: bash scripts/push_photos.sh SUMMARY_JSON   (scripts/deploy.sh step 4b, after bundle deploy)
# Catalog and schema come from the bundle summary variables. Refuses the v2 schema `geologic`. A fresh clone has no
# local photos: then it does nothing. PHOTO_DIR overrides assets/photos (tests).
set -euo pipefail
cd "$(dirname "$0")/.."
SUMMARY="${1:?usage: bash scripts/push_photos.sh SUMMARY_JSON}"
PROFILE=DEFAULT
PHOTO_DIR="${PHOTO_DIR:-assets/photos}"

TARGET_NAMES=$(python3 - "$SUMMARY" <<'PY'
import json, re, sys
v = json.load(open(sys.argv[1])).get("variables") or {}
def val(k):
    e = v.get(k) or {}
    x = e.get("value", e.get("default"))
    return x if isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_]+", x) else None
cat, sch = val("catalog"), val("schema")
if not cat or not sch:
    print(f"push_photos: catalog/schema missing or unsafe in the bundle summary ({v.get('catalog')!r}, {v.get('schema')!r})")
    sys.exit(1)
print(cat, sch)
PY
) || { echo "$TARGET_NAMES"; exit 1; }
read -r CATALOG SCHEMA <<< "$TARGET_NAMES"
if [ "$SCHEMA" = "geologic" ]; then
  echo "push_photos: refusing schema 'geologic' (the live v2 demo)."; exit 1
fi

PHOTOS=()
while IFS= read -r name; do
  if [ -n "$name" ] && [ -f "$PHOTO_DIR/$name" ]; then PHOTOS+=("$name"); fi
done < <(python3 -c 'import sys; sys.path.insert(0, "src"); from geologic.photos import CREDITS; print("\n".join(CREDITS))')
if [ "${#PHOTOS[@]}" -eq 0 ]; then exit 0; fi   # fresh clone: no local photos, nothing to upload

if ! PROBE_ERR=$(databricks volumes read "$CATALOG.$SCHEMA.assets" --profile "$PROFILE" 2>&1 >/dev/null); then
  echo "push_photos: cannot read volume $CATALOG.$SCHEMA.assets: ${PROBE_ERR:-no error output}"
  echo "push_photos: if it does not exist yet, run the setup job (data task), then deploy again."
  exit 0
fi
for name in "${PHOTOS[@]}"; do
  databricks fs cp --overwrite "$PHOTO_DIR/$name" "dbfs:/Volumes/$CATALOG/$SCHEMA/assets/signals/$name" --profile "$PROFILE"
done
echo "push_photos: uploaded ${PHOTOS[*]} to /Volumes/$CATALOG/$SCHEMA/assets/signals"
