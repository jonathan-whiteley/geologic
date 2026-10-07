"""Pre-deploy guard for scripts/deploy.sh: inspect `databricks bundle plan -o json`.

Usage: python3 scripts/check_plan.py PLAN_JSON [--app-exists]
Exit 1 if the plan is missing or empty, deletes/recreates/replaces anything, or (with --app-exists,
meaning the live app is already there) tries to create one of the adopted resources, which means
the checkout is not bound to the live resources yet.
"""
import json
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
  databricks bundle deployment bind geologic geologic --profile DEFAULT
  databricks bundle deployment bind geologic_signals <pipeline_id> --profile DEFAULT
  databricks bundle deployment bind geologic_impact <dashboard_id> --profile DEFAULT
  databricks bundle deployment bind geologic_publish <job_id> --profile DEFAULT
  databricks bundle deployment bind geologic_reset <job_id> --profile DEFAULT
  databricks bundle deployment bind geologic_produce <job_id> --profile DEFAULT"""


def check(doc: dict, app_exists: bool) -> list[str]:
    """Return a list of problems (empty means safe to deploy)."""
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
            problems.append(f"live app exists but plan would create adopted resources {unbound}; checkout is not bound.\n{BIND_HELP}")
    return problems


def main(argv: list[str]) -> int:
    try:
        doc = json.load(open(argv[1]))
    except (OSError, ValueError, IndexError) as e:
        print(f"cannot read plan: {e}")
        return 1
    for k, v in (doc.get("plan") or {}).items():
        print(f"  {str(v.get('action')):>8}  {k}")
    problems = check(doc, "--app-exists" in argv)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
