"""Pre-deploy guards for scripts/deploy.sh.

Usage:
  python3 scripts/check_plan.py PLAN_JSON [--app-exists] [--target T]
  python3 scripts/check_plan.py --summary SUMMARY_JSON --target T [--state-dir DIR]

Plan form (`databricks bundle plan -o json`): exit 1 if the plan is missing or empty, deletes, recreates
or replaces anything, or (with --app-exists, meaning the live app is already there) tries to create one
of the adopted resources, which means the checkout is not bound to the live resources yet.

Summary form (`databricks bundle summary -o json`): exit 1 if a non-dev target resolves to any v2 name
or id (app, schema, Lakebase database, job, pipeline, dashboard, Genie space, serving endpoint), defines a
resource type or task type the guard does not know, has a task without the target's --catalog, --schema
and --lakebase-db, or if the target's bundle state (resources.json for the direct engine, terraform.tfstate
as a fallback) records a different app name (a forced destroy and recreate) or any v2 id.
"""
from __future__ import annotations
import json
import os
import sys

ADOPTED = (
    "resources.apps.geologic",
    "resources.pipelines.geologic_signals",
    "resources.dashboards.geologic_impact",
    "resources.jobs.geologic_publish",
    "resources.jobs.geologic_reset",
    "resources.jobs.geologic_produce",
)
DESTRUCTIVE = ("delete", "recreate", "replace")
BIND_HELP = """Bind the live resources first (README, 'Adopting existing resources'):
  databricks bundle deployment bind geologic <app_name> -t <target> --profile DEFAULT
  databricks bundle deployment bind geologic_signals <pipeline_id> -t <target> --profile DEFAULT
  databricks bundle deployment bind geologic_impact <dashboard_id> -t dev --profile DEFAULT
  databricks bundle deployment bind geologic_publish <job_id> -t <target> --profile DEFAULT
  databricks bundle deployment bind geologic_reset <job_id> -t <target> --profile DEFAULT
  databricks bundle deployment bind geologic_produce <job_id> -t <target> --profile DEFAULT"""

# Live v2 ids (read-only lookups on DEFAULT, 2026-10-21: jobs list, pipelines list-pipelines, lakeview list).
V2_JOB_IDS = {
    "1111928073598072",  # geologic_publish
    "384124888062612",   # geologic_reset
    "958330411388682",   # geologic_produce
    "531891895971748",   # geologic_setup
    "210384212323130",   # geologic_refresh
    "187415563984931",   # geologic_eval
    "481956107571090",   # geologic_verify_uc
    "813926754627330",   # geologic_deploy_strategist
}
V2_PIPELINE_IDS = {"1b9da483-dfed-47fc-9129-a49033fde7bd"}   # geologic-signals
V2_DASHBOARD_IDS = {"01f1c1ae117a1e358fd22c31ac325549"}      # GEOlogic Impact
V2_GENIE = "01f1c1ad57691e9ab2457acf2bff7d78"
V2_ENDPOINTS = {"geologic-content-strategist", "mas-044fdd7b-endpoint"}
V2_IDS = V2_JOB_IDS | V2_PIPELINE_IDS | V2_DASHBOARD_IDS | V2_ENDPOINTS | {V2_GENIE}
EXPECTED = {"v3": {"app": "geologic-v3", "catalog": "jdub_demo", "schema": "geologic_v3", "lakebase_db": "geologic_v3",
                   "job_prefix": "geologic_v3_", "pipeline": "geologic-v3-signals"}}
# Resource types and task types a non-dev target may define; anything else is refused until the guard knows it.
KNOWN_TYPES = {"apps", "jobs", "pipelines"}
KNOWN_TASKS = {"spark_python_task", "pipeline_task"}


def check(doc: dict, app_exists: bool, target: str = "dev") -> list[str]:
    """Return a list of problems with a bundle plan (empty means safe to deploy). Same rules on every target."""
    plan = (doc or {}).get("plan")
    if not plan:
        return ["plan is missing or empty; refusing to deploy without a readable plan"]
    problems = []
    bad = {k: v.get("action") for k, v in plan.items() if v.get("action") in DESTRUCTIVE}
    if bad:
        problems.append(f"plan deletes or recreates resources: {bad}")
    if app_exists:
        unbound = sorted(k for k in ADOPTED if plan.get(k, {}).get("action") == "create")
        if unbound:
            problems.append(f"live app exists but plan for target {target} would create adopted resources {unbound}; "
                            f"checkout is not bound.\n{BIND_HELP}")
    return problems


def _params(task):
    return (task.get("spark_python_task") or {}).get("parameters") or []


def _flag(params: list, name: str):
    """Value after the first `name` in a parameter list (or `name=value`), None when absent."""
    for i, p in enumerate(params):
        if p == name:
            return params[i + 1] if i + 1 < len(params) else None
        if isinstance(p, str) and p.startswith(name + "="):
            return p.split("=", 1)[1]
    return None


def _strings(obj, key=None):
    """Every (key, string value) pair inside a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, key)
    elif isinstance(obj, str):
        yield key, obj


def _v2_refs(obj) -> list[str]:
    """v2 ids, endpoints, the v2 schema or the v2 Lakebase database anywhere inside obj."""
    hits = []
    for k, v in _strings(obj):
        if (v in V2_IDS or v == "jdub_demo.geologic" or v.startswith("jdub_demo.geologic.")
                or (k in ("database_name", "logical_database_name") and v == "geologic")):
            hits.append(f"{k}={v}")
    return hits


def check_summary(summary: dict, target: str) -> list[str]:
    """Problems with a resolved `bundle summary`: v3 may only name v3 resources (Global Constraint 1)."""
    if target == "dev":
        return []
    exp = EXPECTED.get(target)
    if exp is None:
        return [f"unknown target {target!r}; known: dev, {', '.join(EXPECTED)}"]
    res, problems = (summary or {}).get("resources") or {}, []
    for kind in sorted(k for k, v in res.items() if v and k not in KNOWN_TYPES | {"dashboards"}):
        problems.append(f"target {target} defines resource type {kind!r}, which the deploy guard does not check; refusing")
    for key, a in (res.get("apps") or {}).items():
        if a.get("name") != exp["app"]:
            problems.append(f"app name for {key} is {a.get('name')!r}, expected {exp['app']!r}")
        env = {e.get("name"): e.get("value") for e in ((a.get("config") or {}).get("env") or [])}
        for var, want in (("CATALOG_NAME", exp["catalog"]), ("GEOLOGIC_CATALOG", exp["catalog"]),
                          ("SCHEMA_NAME", exp["schema"]), ("GEOLOGIC_SCHEMA", exp["schema"]), ("LAKEBASE_DB", exp["lakebase_db"])):
            if env.get(var) != want:
                problems.append(f"app env {var} is {env.get(var)!r}, expected {want!r}")
        if env.get("GENIE_SPACE_ID") == V2_GENIE:
            problems.append("app env GENIE_SPACE_ID points at the v2 Genie space")
        others = [f"{n}={v}" for n, v in env.items() if v in V2_IDS and n != "GENIE_SPACE_ID"]
        if others:
            problems.append(f"app env {key} names v2 resources: {others}")
        for b in (a.get("resources") or []) + ((a.get("config") or {}).get("resources") or []):
            hits = _v2_refs(b)
            if hits:
                problems.append(f"app {key} resource {b.get('name')!r} binds a v2 resource (Genie, endpoint or job): {hits}")
    for key, j in (res.get("jobs") or {}).items():
        if not str(j.get("name", "")).startswith(exp["job_prefix"]):
            problems.append(f"job name {j.get('name')!r} ({key}) must start with {exp['job_prefix']!r}")
        if str(j.get("id", "")) in V2_JOB_IDS:
            problems.append(f"job {key} is bound to v2 job id {j.get('id')}")
        for t in j.get("tasks") or []:
            tk = f"{key}.{t.get('task_key')}"
            kinds = [k for k in t if k.endswith("_task")]
            unknown = [k for k in kinds if k not in KNOWN_TASKS]
            if unknown or not kinds:
                problems.append(f"task {tk} has task type {unknown or 'none'}, which the deploy guard does not check")
            pid = str((t.get("pipeline_task") or {}).get("pipeline_id", ""))
            if pid in V2_PIPELINE_IDS:
                problems.append(f"task {tk} runs the v2 pipeline id {pid}")
            if t.get("spark_python_task"):
                p = _params(t)
                for flag, want in (("--catalog", exp["catalog"]), ("--schema", exp["schema"]), ("--lakebase-db", exp["lakebase_db"])):
                    got = _flag(p, flag)
                    if got != want:
                        problems.append(f"task {tk} lacks {flag} {want} (has {got!r})")
    for key, p in (res.get("pipelines") or {}).items():
        if p.get("name") != exp["pipeline"] or p.get("schema") != exp["schema"] or p.get("catalog", exp["catalog"]) != exp["catalog"]:
            problems.append(f"pipeline {key} is {p.get('name')!r} on {p.get('catalog')!r}.{p.get('schema')!r}")
        if str(p.get("id", "")) in V2_PIPELINE_IDS:
            problems.append(f"pipeline {key} is bound to the v2 pipeline id {p.get('id')}")
    for key, d in (res.get("dashboards") or {}).items():
        if str((d or {}).get("id", "")) in V2_DASHBOARD_IDS:
            problems.append(f"dashboard {key} is bound to the v2 dashboard id {d.get('id')}")
    if res.get("dashboards"):
        problems.append(f"target {target} must not define dashboards (v2 only)")
    return problems


def check_tfstate(path: str, expected_app: str) -> list[str]:
    """A recorded app name that differs from the resolved one makes terraform destroy and recreate the app."""
    try:
        st = json.load(open(path))
    except (OSError, ValueError):
        return []
    names = [i.get("attributes", {}).get("name") for r in st.get("resources", []) if r.get("type") == "databricks_app"
             for i in r.get("instances", [])]
    return [f"bundle state records app {n!r}, resolved app is {expected_app!r}" for n in names if n != expected_app]


def check_resources_json(path: str, expected_app: str, target: str = "dev") -> list[str]:
    """Direct deployment engine state: state["resources.apps.<key>"]["__id__"] is the app name. On a non-dev
    target any recorded v2 id (a bound v2 resource) is refused too. Raises OSError/ValueError when unreadable."""
    with open(path) as f:
        st = (json.load(f) or {}).get("state") or {}
    problems = []
    for k, v in st.items():
        rid = str((v or {}).get("__id__", ""))
        if k.startswith("resources.apps.") and k.count(".") == 2 and rid != expected_app:
            problems.append(f"bundle state records app {rid!r} for {k}, resolved app is {expected_app!r}")
        if target != "dev" and (rid in V2_IDS or rid.split("/")[-1] in V2_IDS):
            problems.append(f"bundle state for target {target} binds {k} to v2 id {rid}")
    return problems


def check_state(state_dir: str, expected_app: str, target: str = "dev") -> list[str]:
    """Bundle state checks for one target. resources.json (direct engine) first, terraform.tfstate as a fallback.
    No state files means nothing is deployed yet (fine). A state file that exists but cannot be parsed, or a
    deployment.json with no readable state, is refused: the guard must not pass blind."""
    rj = os.path.join(state_dir, "resources.json")
    tf = os.path.join(state_dir, "terraform", "terraform.tfstate")
    if os.path.exists(rj):
        try:
            return check_resources_json(rj, expected_app, target)
        except (OSError, ValueError) as e:
            return [f"cannot parse bundle state {rj}: {e}"]
    if os.path.exists(tf):
        try:
            json.load(open(tf))
        except (OSError, ValueError) as e:
            return [f"cannot parse bundle state {tf}: {e}"]
        return check_tfstate(tf, expected_app)
    if os.path.exists(os.path.join(state_dir, "deployment.json")):
        return [f"{state_dir} has deployment.json but neither resources.json nor terraform/terraform.tfstate; refusing"]
    return []


def _opt(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def _main_summary(argv: list[str]) -> int:
    target, state_dir = _opt(argv, "--target"), _opt(argv, "--state-dir")
    if not target:
        print("--summary needs --target")
        return 1
    try:
        summary = json.load(open(_opt(argv, "--summary") or ""))
    except (OSError, ValueError) as e:
        print(f"cannot read bundle summary: {e}")
        return 1
    problems = check_summary(summary, target)
    apps = (summary.get("resources") or {}).get("apps") or {}
    app_name = (apps.get("geologic") or {}).get("name")
    if state_dir and app_name:
        problems += check_state(state_dir, app_name, target)
    for p in problems:
        print(p)
    if not problems:
        print(f"bundle summary for target {target}: OK (app {app_name!r})")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    if "--summary" in argv:
        return _main_summary(argv)
    try:
        doc = json.load(open(argv[1]))
    except (OSError, ValueError, IndexError) as e:
        print(f"cannot read plan: {e}")
        return 1
    for k, v in (doc.get("plan") or {}).items():
        print(f"  {str(v.get('action')):>8}  {k}")
    problems = check(doc, "--app-exists" in argv, _opt(argv, "--target") or "dev")
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
