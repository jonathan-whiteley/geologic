"""Create or update the GEOlogic v3 Genie space from genie/space.json.

Usage:
  python3 scripts/genie_space.py --target v3 --create
  python3 scripts/genie_space.py --target v3 --update --space-id <id>

{{schema}} renders to the target's catalog.schema (bundle summary). The dev target and the live v2 space are refused.
--create prints the new space_id; set it as targets.v3.variables.genie_space_id in databricks.yml and redeploy.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "src"))
from geologic.sqlfiles import render  # noqa: E402

PROFILE = "DEFAULT"
WAREHOUSE_ID = "0168e23e24e6ae10"
V2_SPACE_ID = "01f1c1ad57691e9ab2457acf2bff7d78"
TITLE = "GEOlogic v3"
DESCRIPTION = "GEOlogic v3 metrics on 30 tracked prompts"
SPACE_FILE = os.path.join(_here, "..", "genie", "space.json")


def _cli(*args: str) -> dict:
    out = subprocess.run(["databricks", *args, "--profile", PROFILE, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"databricks {' '.join(args[:3])} failed: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "{}")


def refusal(target: str, space_id: str | None) -> str | None:
    if target == "dev":
        return "Refusing --target dev: it is the live v2 demo."
    if space_id == V2_SPACE_ID:
        return f"Refusing the v2 Genie space {V2_SPACE_ID}."
    return None


def serialized(catalog: str, schema: str, path: str = SPACE_FILE) -> str:
    with open(path) as f:
        space = json.loads(render(f.read(), catalog=catalog, schema=schema))
    return json.dumps(space)


def create_body(serialized_space: str) -> dict:
    return {"warehouse_id": WAREHOUSE_ID, "title": TITLE, "description": DESCRIPTION, "serialized_space": serialized_space}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--update", action="store_true")
    ap.add_argument("--space-id")
    a = ap.parse_args(argv)
    problem = refusal(a.target, a.space_id)
    if problem:
        print(problem)
        return 1
    if a.update and not a.space_id:
        ap.error("--update needs --space-id")
    v = _cli("bundle", "summary", "-t", a.target).get("variables") or {}
    get = lambda n: (v.get(n) or {}).get("value", (v.get(n) or {}).get("default"))
    catalog, schema = get("catalog"), get("schema")
    if schema in (None, "geologic"):
        print(f"Refusing schema {schema!r}: the v2 schema is jdub_demo.geologic.")
        return 1
    space = serialized(catalog, schema)
    if a.create:
        r = _cli("api", "post", "/api/2.0/genie/spaces", "--json", json.dumps(create_body(space)))
        print(r.get("space_id") or json.dumps(r))
    else:
        _cli("api", "patch", f"/api/2.0/genie/spaces/{a.space_id}", "--json", json.dumps({"serialized_space": space}))
        print(f"updated {a.space_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
