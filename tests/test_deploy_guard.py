import importlib.util, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_plan", ROOT / "scripts" / "check_plan.py")
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

def _summary(app="geologic-v3", schema="geologic_v3", db="geologic_v3", job="geologic_v3_setup", pipe="geologic-v3-signals",
             job_id=None, dashboards=None, genie="none"):
    env = [{"name": "SCHEMA_NAME", "value": schema}, {"name": "GEOLOGIC_SCHEMA", "value": schema},
           {"name": "LAKEBASE_DB", "value": db}, {"name": "GENIE_SPACE_ID", "value": genie}]
    task = {"task_key": "data", "spark_python_task": {"python_file": "x.py", "parameters": ["--catalog", "jdub_demo", "--schema", schema, "--lakebase-db", db]}}
    j = {"name": job, "tasks": [task]}
    if job_id: j["id"] = job_id
    res = {"apps": {"geologic": {"name": app, "config": {"env": env}}}, "jobs": {"geologic_setup": j},
           "pipelines": {"geologic_signals": {"name": pipe, "schema": schema}}}
    if dashboards: res["dashboards"] = dashboards
    return {"resources": res}

def test_v3_summary_ok():
    assert cp.check_summary(_summary(), "v3") == []

def test_v3_refuses_every_v2_name():
    bad = _summary(app="geologic", schema="geologic", db="geologic", job="geologic_setup", pipe="geologic-signals",
                   job_id="1111928073598072", dashboards={"geologic_impact": {}}, genie="01f1c1ad57691e9ab2457acf2bff7d78")
    problems = " | ".join(cp.check_summary(bad, "v3"))
    for needle in ("app name", "SCHEMA_NAME", "LAKEBASE_DB", "job name", "v2 job id", "pipeline", "dashboards", "Genie"):
        assert needle in problems, needle

def test_v3_refuses_job_task_without_schema_param():
    s = _summary(); s["resources"]["jobs"]["geologic_setup"]["tasks"][0]["spark_python_task"]["parameters"] = []
    assert any("--schema" in p for p in cp.check_summary(s, "v3"))

def test_unknown_target_refused():
    assert cp.check_summary(_summary(), "prod")

def test_tfstate_app_name_mismatch(tmp_path):
    st = {"resources": [{"type": "databricks_app", "instances": [{"attributes": {"name": "geologic"}}]}]}
    p = tmp_path / "terraform.tfstate"; p.write_text(json.dumps(st))
    assert cp.check_tfstate(str(p), "geologic-v3") and cp.check_tfstate(str(p), "geologic") == []
    assert cp.check_tfstate(str(tmp_path / "missing.tfstate"), "geologic-v3") == []

def test_plan_check_still_refuses_destructive():
    assert cp.check({"plan": {"resources.apps.geologic": {"action": "recreate"}}}, False, "v3")
    assert cp.check({"plan": {"resources.apps.geologic": {"action": "create"}}}, False, "v3") == []
