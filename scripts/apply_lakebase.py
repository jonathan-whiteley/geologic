"""Run Lakebase SQL for a bundle target: create the database, apply a schema file, grant an app service principal, or query.

Usage:
  python3 scripts/apply_lakebase.py --target v3 --create-db sql/lakebase_schema.sql
  python3 scripts/apply_lakebase.py --target v3 --grant-sp <APP_SP_CLIENT_ID>
  python3 scripts/apply_lakebase.py --target v3 --query "SELECT epoch FROM demo_state"

lakebase_db and lakebase_host come from `databricks bundle summary -t <target>`. The v2 database `geologic` is refused
(Global Constraint 1). The password is a fresh database credential for instance geologic; psql runs with ON_ERROR_STOP.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import uuid

PROFILE = "DEFAULT"
INSTANCE = "geologic"
V2_DB = "geologic"
_CLIENT_ID = re.compile(r"^[0-9a-f-]{36}$")


def _cli(*args: str) -> dict:
    out = subprocess.run(["databricks", *args, "--profile", PROFILE, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"databricks {' '.join(args[:3])} failed: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "{}")


def bundle_vars(target: str) -> dict:
    v = _cli("bundle", "summary", "-t", target).get("variables") or {}
    get = lambda n: (v.get(n) or {}).get("value", (v.get(n) or {}).get("default"))
    vals = {n: get(n) for n in ("lakebase_db", "lakebase_host")}
    missing = [n for n, x in vals.items() if not x]
    if missing:
        raise SystemExit(f"bundle summary for target {target} has no value for {missing}")
    return vals


def target_problem(db: str) -> str | None:
    return "refusing the v2 database geologic" if db == V2_DB else None


def grant_statements(client_id: str, db: str) -> list[str]:
    if not _CLIENT_ID.match(client_id or ""):
        raise ValueError(f"not a service principal client id: {client_id!r}")
    sp = f'"{client_id}"'
    return [
        "CREATE EXTENSION IF NOT EXISTS databricks_auth",
        f"SELECT databricks_create_role('{client_id}', 'SERVICE_PRINCIPAL')",
        f"GRANT CONNECT ON DATABASE {db} TO {sp}",
        f"GRANT USAGE, CREATE ON SCHEMA public TO {sp}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {sp}",
        f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {sp}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {sp}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {sp}",
    ]


# The role may already exist (created earlier, or by `databricks postgres create-role` on the Autoscaling branch).
_TOLERATED = ("already exists",)


def _psql(host, user, token, db, *args) -> subprocess.CompletedProcess:
    conn = f"host={host} user={user} dbname={db} sslmode=require"
    return subprocess.run(["psql", conn, "-v", "ON_ERROR_STOP=1", *args], capture_output=True, text=True,
                          env={**os.environ, "PGPASSWORD": token})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--create-db", action="store_true")
    ap.add_argument("--grant-sp", metavar="CLIENT_ID")
    ap.add_argument("--query")
    ap.add_argument("file", nargs="?")
    a = ap.parse_args(argv)
    if not (a.create_db or a.grant_sp or a.query or a.file):
        ap.error("give --create-db, --grant-sp, --query or a SQL file")
    if a.grant_sp and not _CLIENT_ID.match(a.grant_sp):
        print(f"not a service principal client id: {a.grant_sp!r}")
        return 1
    v = bundle_vars(a.target)
    db, host = v["lakebase_db"], v["lakebase_host"]
    problem = target_problem(db)
    if problem:
        print(problem)
        return 1
    token = _cli("database", "generate-database-credential", "--json",
                 json.dumps({"instance_names": [INSTANCE], "request_id": str(uuid.uuid4())}))["token"]
    user = _cli("current-user", "me")["userName"]

    def run(target_db, *args, tolerate=()):
        r = _psql(host, user, token, target_db, *args)
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).strip()
            if any(t in msg for t in tolerate):
                print(f"ok (tolerated): {msg.splitlines()[-1] if msg else ''}")
                return True
            print(f"FAILED: {msg}")
            return False
        if r.stdout.strip():
            print(r.stdout.rstrip())
        return True

    if a.create_db and not run("databricks_postgres", "-c", f"CREATE DATABASE {db}", tolerate=_TOLERATED):
        return 1
    if a.file and not run(db, "-f", a.file):
        return 1
    if a.grant_sp:
        for i, s in enumerate(grant_statements(a.grant_sp, db)):
            if not run(db, "-c", s, tolerate=_TOLERATED if i < 2 else ()):
                return 1
            print(f"OK {s[:70]}")
    if a.query and not run(db, "-c", a.query):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
