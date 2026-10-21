import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("rehearse", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "rehearse.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

def test_summarize_runs():
    assert r.summarize_runs([41.2, 38.0, 52.9, 44.1, 39.5])[0] is True
    ok, msg = r.summarize_runs([41.2, None, 52.9, 61.0, 39.5])
    assert ok is False and "2 of 5" in msg


def test_summarize_runs_edges():
    ok, msg = r.summarize_runs([41.2, 38.0, 52.9, 44.1, 39.5])
    assert "5 of 5 under 60 s" in msg
    assert r.summarize_runs([])[0] is False
    assert r.summarize_runs([60.0])[0] is False   # strictly under the limit


def test_pick_party_pack_patch():
    fixes = [{"fix_id": "a", "asset_type": "correction_email", "issue_type": "outdated", "title": "Game Day Party Pack"},
             {"fix_id": "b", "asset_type": "owned_patch", "issue_type": "wrong", "title": "Classic Pepperoni"},
             {"fix_id": "c", "asset_type": "owned_patch", "issue_type": "outdated", "title": "partyplanner-weekly.com lists the Game Day Party Pack"}]
    assert r.pick_fix(fixes) == "c"
    assert r.pick_fix(fixes, "b") == "b"
    assert r.pick_fix([f for f in fixes if f["fix_id"] != "c"]) is None


def test_refuses_other_apps():
    assert r.app_problem("geologic-v3") is None
    assert r.app_problem("geologic") is not None
