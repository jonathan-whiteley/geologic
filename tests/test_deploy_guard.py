import importlib.util, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_plan", ROOT / "scripts" / "check_plan.py")
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

def _summary(app="geologic-v3", schema="geologic_v3", db="geologic_v3", job="geologic_v3_setup", pipe="geologic-v3-signals",
             job_id=None, dashboards=None, genie="none"):
    env = [{"name": "CATALOG_NAME", "value": "jdub_demo"}, {"name": "GEOLOGIC_CATALOG", "value": "jdub_demo"},
           {"name": "SCHEMA_NAME", "value": schema}, {"name": "GEOLOGIC_SCHEMA", "value": schema},
           {"name": "LAKEBASE_DB", "value": db}, {"name": "GENIE_SPACE_ID", "value": genie}]
    task = {"task_key": "data", "spark_python_task": {"python_file": "x.py", "parameters": ["--catalog", "jdub_demo", "--schema", schema, "--lakebase-db", db]}}
    j = {"name": job, "tasks": [task]}
    if job_id: j["id"] = job_id
    binds = [{"name": "sql-warehouse", "sql_warehouse": {"id": "0168e23e24e6ae10", "permission": "CAN_USE"}},
             {"name": "publish-job", "job": {"id": "${resources.jobs.geologic_publish.id}", "permission": "CAN_MANAGE_RUN"}}]
    res = {"apps": {"geologic": {"name": app, "config": {"env": env}, "resources": binds}}, "jobs": {"geologic_setup": j},
           "pipelines": {"geologic_signals": {"name": pipe, "catalog": "jdub_demo", "schema": schema}}}
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


def _task(s):
    return s["resources"]["jobs"]["geologic_setup"]["tasks"][0]

def test_v3_refuses_wrong_or_missing_lakebase_db_and_catalog():
    s = _summary(); _task(s)["spark_python_task"]["parameters"] = ["--catalog", "jdub_demo", "--schema", "geologic_v3"]
    assert any("--lakebase-db" in p for p in cp.check_summary(s, "v3"))          # missing: apply_job_defaults would fill in geologic
    s = _summary(); _task(s)["spark_python_task"]["parameters"][5] = "geologic"
    assert any("--lakebase-db geologic_v3" in p for p in cp.check_summary(s, "v3"))
    s = _summary(); _task(s)["spark_python_task"]["parameters"][1] = "other_catalog"
    assert any("--catalog jdub_demo" in p for p in cp.check_summary(s, "v3"))
    s = _summary(); _task(s)["spark_python_task"]["parameters"] = ["--schema", "geologic_v3", "--lakebase-db=geologic_v3"]
    assert [p for p in cp.check_summary(s, "v3") if "--lakebase-db" in p] == []   # --flag=value form counts
    assert any("--catalog" in p for p in cp.check_summary(s, "v3"))

def test_v3_refuses_unknown_resource_and_task_types():
    for kind in ("experiments", "model_serving_endpoints", "schemas", "volumes", "database_catalogs", "synced_database_tables"):
        s = _summary(); s["resources"][kind] = {"x": {"name": "anything"}}
        assert any(repr(kind) in p for p in cp.check_summary(s, "v3")), kind
    s = _summary(); s["resources"]["schemas"] = {}                               # an empty section defines nothing
    assert cp.check_summary(s, "v3") == []
    s = _summary(); _task(s).pop("spark_python_task"); _task(s)["notebook_task"] = {"notebook_path": "/x"}
    assert any("task type" in p for p in cp.check_summary(s, "v3"))

def test_v3_refuses_app_bindings_to_v2():
    for bind in ({"name": "strategist", "serving_endpoint": {"name": "geologic-content-strategist", "permission": "CAN_QUERY"}},
                 {"name": "supervisor", "serving_endpoint": {"name": "mas-044fdd7b-endpoint", "permission": "CAN_QUERY"}},
                 {"name": "publish-job", "job": {"id": "1111928073598072", "permission": "CAN_MANAGE_RUN"}},
                 {"name": "genie", "genie_space": {"space_id": "01f1c1ad57691e9ab2457acf2bff7d78", "permission": "CAN_RUN"}},
                 {"name": "db", "database": {"instance_name": "geologic", "database_name": "geologic", "permission": "CAN_CONNECT_AND_CREATE"}}):
        s = _summary(); s["resources"]["apps"]["geologic"]["resources"].append(bind)
        assert any("binds a v2 resource" in p for p in cp.check_summary(s, "v3")), bind["name"]

def test_v3_refuses_v2_pipeline_and_dashboard_ids():
    s = _summary(); s["resources"]["pipelines"]["geologic_signals"]["id"] = "1b9da483-dfed-47fc-9129-a49033fde7bd"
    assert any("v2 pipeline id" in p for p in cp.check_summary(s, "v3"))
    s = _summary(); s["resources"]["jobs"]["geologic_setup"]["tasks"].append(
        {"task_key": "p1", "pipeline_task": {"pipeline_id": "1b9da483-dfed-47fc-9129-a49033fde7bd"}})
    assert any("runs the v2 pipeline id" in p for p in cp.check_summary(s, "v3"))
    s = _summary(dashboards={"geologic_impact": {"id": "01f1c1ae117a1e358fd22c31ac325549"}})
    assert any("v2 dashboard id" in p for p in cp.check_summary(s, "v3"))

def _resources_json(tmp_path, entries):
    d = tmp_path / "state"; d.mkdir(exist_ok=True)
    (d / "resources.json").write_text(json.dumps({"state_version": 1, "state": entries}))
    return str(d)

def test_state_resources_json_app_name(tmp_path):
    ok = _resources_json(tmp_path, {"resources.apps.geologic": {"__id__": "geologic-v3", "state": {}},
                                    "resources.jobs.geologic_setup": {"__id__": "42", "state": {}}})
    assert cp.check_state(ok, "geologic-v3", "v3") == []
    bad = _resources_json(tmp_path, {"resources.apps.geologic": {"__id__": "geologic", "state": {}}})
    assert any("records app 'geologic'" in p for p in cp.check_state(bad, "geologic-v3", "v3"))

def test_state_resources_json_refuses_bound_v2_ids(tmp_path):
    d = _resources_json(tmp_path, {"resources.apps.geologic": {"__id__": "geologic-v3", "state": {}},
                                   "resources.jobs.geologic_publish": {"__id__": "1111928073598072", "state": {}},
                                   "resources.jobs.geologic_publish.permissions": {"__id__": "/jobs/1111928073598072", "state": {}}})
    assert len([p for p in cp.check_state(d, "geologic-v3", "v3") if "v2 id" in p]) == 2
    assert cp.check_state(d, "geologic-v3", "dev") == []                         # dev owns those ids

def test_state_unreadable_or_missing(tmp_path):
    d = tmp_path / "state"; d.mkdir()
    assert cp.check_state(str(d), "geologic-v3", "v3") == []                    # nothing deployed yet
    (d / "deployment.json").write_text("{}")
    assert cp.check_state(str(d), "geologic-v3", "v3")                          # deployed, but no readable state
    (d / "resources.json").write_text("not json")
    assert any("cannot parse" in p for p in cp.check_state(str(d), "geologic-v3", "v3"))
    (d / "resources.json").unlink(); (d / "terraform").mkdir(); (d / "terraform" / "terraform.tfstate").write_text("{")
    assert any("cannot parse" in p for p in cp.check_state(str(d), "geologic-v3", "v3"))
    st = {"resources": [{"type": "databricks_app", "instances": [{"attributes": {"name": "geologic"}}]}]}
    (d / "terraform" / "terraform.tfstate").write_text(json.dumps(st))          # tfstate fallback still checked
    assert cp.check_state(str(d), "geologic-v3", "v3") and cp.check_state(str(d), "geologic", "v3") == []

def test_main_summary_reads_state_dir(tmp_path):
    summ = tmp_path / "s.json"; summ.write_text(json.dumps(_summary()))
    d = _resources_json(tmp_path, {"resources.apps.geologic": {"__id__": "geologic", "state": {}}})
    assert cp.main(["check_plan.py", "--summary", str(summ), "--target", "v3", "--state-dir", d]) == 1
    d2 = tmp_path / "fresh"; d2.mkdir()
    assert cp.main(["check_plan.py", "--summary", str(summ), "--target", "v3", "--state-dir", str(d2)]) == 0


# check_plan.check (plan actions), moved verbatim from tests/test_fix2.py
def test_empty_or_missing_plan_fails():
    assert cp.check({}, False) and cp.check({"plan": {}}, True)


def test_destructive_actions_refused():
    assert cp.check({"plan": {"resources.jobs.x": {"action": "recreate"}}}, False)
    assert cp.check({"plan": {"resources.jobs.x": {"action": "delete"}}}, False)


def test_update_and_skip_pass():
    assert cp.check({"plan": {"resources.apps.geologic": {"action": "update"}, "resources.jobs.a": {"action": "skip"}}}, True) == []


def test_create_of_adopted_refused_only_when_app_exists():
    doc = {"plan": {"resources.jobs.geologic_publish": {"action": "create"}}}
    assert cp.check(doc, True)
    assert cp.check(doc, False) == []
    # creating a non-adopted resource is fine even with a live app
    assert cp.check({"plan": {"resources.jobs.geologic_setup": {"action": "create"}}}, True) == []


def test_main_exit_codes(tmp_path):
    f = tmp_path / "p.json"; f.write_text(json.dumps({"plan": {"resources.apps.geologic": {"action": "create"}}}))
    assert cp.main(["x", str(f), "--app-exists"]) == 1
    assert cp.main(["x", str(f)]) == 0
    assert cp.main(["x", str(tmp_path / "missing.json")]) == 1


def test_dropped_eval_job_delete_is_refused_on_every_target():
    # The MLflow eval job left resources/jobs.yml (Task 10 cut). On dev its state is bound to the v2 job
    # 187415563984931, on v3 to geologic_v3_eval: the resulting delete must stop deploy.sh, never run.
    doc = {"plan": {"resources.jobs.geologic_eval": {"action": "delete"}, "resources.apps.geologic": {"action": "update"}}}
    for target in ("dev", "v3"):
        assert any("deletes" in p for p in cp.check(doc, True, target)), target
    assert "187415563984931" in cp.V2_JOB_IDS


def test_jobs_yml_has_no_eval_job():
    jobs = (ROOT / "resources" / "jobs.yml").read_text()
    assert "geologic_eval" not in jobs and "evaluate_drafts" not in jobs
    assert not (ROOT / "jobs" / "evaluate_drafts.py").exists()


def test_every_python_task_passes_its_stack_explicitly():   # final review I3: v2 (dev) keeps 'geologic' only by passing it
    import re
    jobs = (ROOT / "resources" / "jobs.yml").read_text()
    flags = '"--catalog", "${var.catalog}", "--schema", "${var.schema}", "--lakebase-db", "${var.lakebase_db}"'
    assert jobs.count("python_file:") == jobs.count(flags) > 0
    app = (ROOT / "resources" / "app.yml").read_text()
    for var, ref in (("SCHEMA_NAME", "schema"), ("GEOLOGIC_SCHEMA", "schema"), ("LAKEBASE_DB", "lakebase_db")):
        assert f'{{ name: {var}, value: "${{var.{ref}}}" }}' in app, var
    top = (ROOT / "databricks.yml").read_text().split("targets:")[0]
    assert re.search(r"\n  schema:\n    default: geologic\n", top) and re.search(r"\n  lakebase_db:\n(?:    .*\n)*?    default: geologic\n", top)
