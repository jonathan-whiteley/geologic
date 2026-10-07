import importlib.util
import json
from pathlib import Path

from geologic.drafting import baseline_blocked, eval_failures

_spec = importlib.util.spec_from_file_location("check_plan", Path(__file__).parent.parent / "scripts" / "check_plan.py")
cp = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cp)


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


def test_baseline_blocked():
    assert baseline_blocked(["opp1"]) and not baseline_blocked([])


def test_eval_thresholds():
    ok = {"no_competitors/mean": 1.0, "valid_jsonld/mean": 1.0, "brand_voice/mean": 0.8}
    assert eval_failures(ok) == []
    assert len(eval_failures({**ok, "brand_voice/mean": 0.79})) == 1
    assert len(eval_failures({**ok, "no_competitors/mean": 0.95})) == 1
    assert len(eval_failures({"brand_voice/mean": 1.0})) == 2  # missing metrics fail
