"""Pre-deploy guards for scripts/deploy.sh.

Usage:
  python3 scripts/check_plan.py PLAN_JSON [--app-exists] [--target T]
  python3 scripts/check_plan.py --summary SUMMARY_JSON --target T [--state-dir DIR]

Plan form (`databricks bundle plan -o json`): exit 1 if the plan is missing or empty, deletes, recreates
or replaces anything, or (with --app-exists, meaning the live app is already there) tries to create one
of the adopted resources, which means the checkout is not bound to the live resources yet.

Summary form (`databricks bundle summary -o json`): exit 1 if a non-dev target resolves to any v2 name
(app, schema, Lakebase database, job, pipeline, dashboard, Genie space), a job task lacks the target's
--schema parameter, or the target's terraform state records a different app name (which would make
terraform destroy and recreate the app).
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

V2_JOB_IDS = {"1111928073598072", "384124888062612", "958330411388682"}
V2_GENIE = "01f1c1ad57691e9ab2457acf2bff7d78"
EXPECTED = {"v3": {"app": "geologic-v3", "schema": "geologic_v3", "lakebase_db": "geologic_v3",
                   "job_prefix": "geologic_v3_", "pipeline": "geologic-v3-signals"}}


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


def check_summary(summary: dict, target: str) -> list[str]:
    """Problems with a resolved `bundle summary`: v3 may only name v3 resources (Global Constraint 1)."""
    if target == "dev":
        return []
    exp = EXPECTED.get(target)
    if exp is None:
        return [f"unknown target {target!r}; known: dev, {', '.join(EXPECTED)}"]
    res, problems = (summary or {}).get("resources") or {}, []
    for key, a in (res.get("apps") or {}).items():
        if a.get("name") != exp["app"]:
            problems.append(f"app name for {key} is {a.get('name')!r}, expected {exp['app']!r}")
        env = {e.get("name"): e.get("value") for e in ((a.get("config") or {}).get("env") or [])}
        for var, want in (("SCHEMA_NAME", exp["schema"]), ("GEOLOGIC_SCHEMA", exp["schema"]), ("LAKEBASE_DB", exp["lakebase_db"])):
            if env.get(var) != want:
                problems.append(f"app env {var} is {env.get(var)!r}, expected {want!r}")
        if env.get("GENIE_SPACE_ID") == V2_GENIE:
            problems.append("app env GENIE_SPACE_ID points at the v2 Genie space")
    for key, j in (res.get("jobs") or {}).items():
        if not str(j.get("name", "")).startswith(exp["job_prefix"]):
            problems.append(f"job name {j.get('name')!r} ({key}) must start with {exp['job_prefix']!r}")
        if str(j.get("id", "")) in V2_JOB_IDS:
            problems.append(f"job {key} is bound to v2 job id {j.get('id')}")
        for t in j.get("tasks") or []:
            p = _params(t)
            if t.get("spark_python_task") and not any(p[i] == "--schema" and p[i + 1] == exp["schema"] for i in range(len(p) - 1)):
                problems.append(f"task {key}.{t.get('task_key')} lacks --schema {exp['schema']}")
    for key, p in (res.get("pipelines") or {}).items():
        if p.get("name") != exp["pipeline"] or p.get("schema") != exp["schema"]:
            problems.append(f"pipeline {key} is {p.get('name')!r} on schema {p.get('schema')!r}")
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
        problems += check_tfstate(os.path.join(state_dir, "terraform", "terraform.tfstate"), app_name)
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
