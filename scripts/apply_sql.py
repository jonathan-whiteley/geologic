"""Run repo SQL files (or one query) on the target's warehouse through the SQL Statement API.

Usage:
  python3 scripts/apply_sql.py --target v3 sql/views.sql sql/metric_views.sql
  python3 scripts/apply_sql.py --target v3 --query "SELECT count(*) AS n FROM {{schema}}.prompt_bank"

catalog, schema and warehouse_id come from `databricks bundle summary -t <target>`, and {{schema}} and
{{usage_app}} render per geologic.sqlfiles. Statements go as JSON bodies to /api/2.0/sql/statements,
which keeps metric-view YAML indentation intact. --target dev (the live v2 demo) needs --allow-v2.
--query prints each result row as one JSON object per line.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from geologic.sqlfiles import render, split_statements  # noqa: E402

PROFILE = "DEFAULT"
POLL_S, MAX_WAIT_S = 3, 300


def _cli(*args: str) -> dict:
    out = subprocess.run(["databricks", *args, "--profile", PROFILE], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"databricks {' '.join(args[:3])} failed: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "{}")


def bundle_vars(target: str) -> dict:
    summary = _cli("bundle", "summary", "-t", target, "-o", "json")
    v = summary.get("variables") or {}
    get = lambda n: (v.get(n) or {}).get("value", (v.get(n) or {}).get("default"))
    vals = {n: get(n) for n in ("catalog", "schema", "warehouse_id")}
    missing = [n for n, x in vals.items() if not x]
    if missing:
        raise SystemExit(f"bundle summary for target {target} has no value for {missing}")
    return vals


def execute(statement: str, warehouse_id: str) -> dict:
    body = {"warehouse_id": warehouse_id, "statement": statement, "wait_timeout": "50s"}
    r = _cli("api", "post", "/api/2.0/sql/statements", "--json", json.dumps(body))
    waited = 0
    while (r.get("status") or {}).get("state") in ("PENDING", "RUNNING") and waited < MAX_WAIT_S:
        time.sleep(POLL_S)
        waited += POLL_S
        r = _cli("api", "get", f"/api/2.0/sql/statements/{r['statement_id']}")
    return r


def _failed(r: dict) -> str | None:
    st = r.get("status") or {}
    if st.get("state") == "SUCCEEDED":
        return None
    return (st.get("error") or {}).get("message") or f"statement ended in state {st.get('state')}"


def rows(r: dict) -> list[dict]:
    cols = [c["name"] for c in ((r.get("manifest") or {}).get("schema") or {}).get("columns") or []]
    return [dict(zip(cols, row)) for row in ((r.get("result") or {}).get("data_array") or [])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--allow-v2", action="store_true", help="permit --target dev (the live v2 demo)")
    ap.add_argument("--query", help="one SELECT; rows print as JSON lines")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args(argv)
    if a.target == "dev" and not a.allow_v2:
        print("Refusing --target dev: it is the live v2 demo. Pass --allow-v2 only from the v2 branch.")
        return 1
    if not a.files and not a.query:
        ap.error("give SQL files or --query")
    v = bundle_vars(a.target)
    if a.query:
        r = execute(render(a.query, catalog=v["catalog"], schema=v["schema"]), v["warehouse_id"])
        err = _failed(r)
        if err:
            print(f"FAILED: {err}")
            return 1
        for row in rows(r):
            print(json.dumps(row))
        return 0
    for path in a.files:
        with open(path) as f:
            stmts = split_statements(render(f.read(), catalog=v["catalog"], schema=v["schema"]))
        for s in stmts:
            err = _failed(execute(s, v["warehouse_id"]))
            head = " ".join(s.split())[:60]
            if err:
                print(f"FAILED {head}: {err}")
                return 1
            print(f"OK {head}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
