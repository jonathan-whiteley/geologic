"""scripts/deploy.sh refusals, run with stub databricks/npm/rsync/git first on PATH so no real CLI is ever called."""
import os, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _run(tmp_path, branch="build/v3", **env):
    bin_, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_.mkdir(exist_ok=True)
    for tool in ("databricks", "npm", "rsync"):
        (bin_ / tool).write_text(f'#!/bin/sh\necho "{tool} $*" >> "{log}"\nexit 99\n')
    (bin_ / "git").write_text(f'#!/bin/sh\necho "git $*" >> "{log}"\necho "{branch}"\n')
    for f in bin_.iterdir():
        f.chmod(0o755)
    e = {k: v for k, v in os.environ.items() if k not in ("TARGET", "ALLOW_V2_DEPLOY")}
    e.update(env, PATH=f"{bin_}:{os.environ['PATH']}")
    r = subprocess.run(["bash", "scripts/deploy.sh"], cwd=ROOT, env=e, capture_output=True, text=True)
    calls = [c for c in (log.read_text().splitlines() if log.exists() else []) if not c.startswith("git ")]
    return r, calls

def test_unset_target_refused(tmp_path):
    r, calls = _run(tmp_path)
    assert r.returncode == 1 and "Set TARGET, for example: TARGET=v3 bash scripts/deploy.sh" in r.stdout and calls == []

def test_dev_refused_without_allow(tmp_path):
    r, calls = _run(tmp_path, branch="main", TARGET="dev")
    assert r.returncode == 1 and "Refusing TARGET=dev" in r.stdout and calls == []

def test_dev_refused_on_build_v3_even_with_allow(tmp_path):
    r, calls = _run(tmp_path, TARGET="dev", ALLOW_V2_DEPLOY="1")
    assert r.returncode == 1 and "build/v3" in r.stdout and calls == []

def test_v3_first_cli_call_is_the_summary_guard(tmp_path):
    r, calls = _run(tmp_path, TARGET="v3")
    assert r.returncode == 99 and calls == ["databricks bundle summary -o json -t v3 --profile DEFAULT"]


# Smoke 1 F3a: scripts/push_photos.sh (deploy.sh step 4b) uploads the credited photos found locally to the target's
# volume, refuses the v2 schema and never reaches the real CLI (stub databricks first on PATH).
import json

def _push(tmp_path, schema="geologic_v3", catalog="jdub_demo", photos=("goff_slices_n_stix.jpg",),
          volume_exists=True):
    bin_, log, pdir = tmp_path / "bin", tmp_path / "calls.log", tmp_path / "photos"
    bin_.mkdir(exist_ok=True); pdir.mkdir(exist_ok=True)
    for p in photos:
        (pdir / p).write_bytes(b"x")
    for p in ("barkley_press.jpg", "kittle_tailgate.png"):   # not in CREDITS: never uploaded
        (pdir / p).write_bytes(b"x")
    rc = 0 if volume_exists else 1
    (bin_ / "databricks").write_text(f'#!/bin/sh\necho "databricks $*" >> "{log}"\n'
                                     f'case "$1" in volumes) [ {rc} = 0 ] || echo "Error: RESOURCE_DOES_NOT_EXIST" >&2; exit {rc};; fs) exit 0;; *) exit 99;; esac\n')
    (bin_ / "databricks").chmod(0o755)
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"variables": {"catalog": {"default": "jdub_demo", "value": catalog},
                                                 "schema": {"default": "geologic", "value": schema}},
                                   "resources": {"apps": {"geologic": {"name": "geologic-v3"}}}}))
    e = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "PHOTO_DIR": str(pdir)}
    r = subprocess.run(["bash", "scripts/push_photos.sh", str(summary)], cwd=ROOT, env=e, capture_output=True, text=True)
    return r, (log.read_text().splitlines() if log.exists() else [])

def test_push_photos_copies_credited_photos_to_the_v3_volume(tmp_path):
    r, calls = _push(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    pdir = tmp_path / "photos"
    assert calls == ["databricks volumes read jdub_demo.geologic_v3.assets --profile DEFAULT",
                     f"databricks fs cp --overwrite {pdir}/goff_slices_n_stix.jpg "
                     "dbfs:/Volumes/jdub_demo/geologic_v3/assets/signals/goff_slices_n_stix.jpg --profile DEFAULT"]

def test_push_photos_refuses_the_v2_schema(tmp_path):
    r, calls = _push(tmp_path, schema="geologic")
    assert r.returncode == 1 and "geologic" in r.stdout and calls == []

def test_push_photos_refuses_unsafe_or_missing_names(tmp_path):
    for schema in ("", "geologic_v3; rm -rf /", None):
        r, calls = _push(tmp_path, schema=schema)
        assert r.returncode == 1 and calls == [], schema

def test_push_photos_skips_silently_without_local_photos(tmp_path):
    r, calls = _push(tmp_path, photos=())
    assert r.returncode == 0 and calls == [] and r.stdout == ""

def test_push_photos_skips_when_the_volume_does_not_exist_yet(tmp_path):
    r, calls = _push(tmp_path, volume_exists=False)
    assert r.returncode == 0 and "setup" in r.stdout and not [c for c in calls if "fs cp" in c]
    assert "RESOURCE_DOES_NOT_EXIST" in r.stdout   # the probe's stderr is shown, not discarded

def test_deploy_sh_pushes_photos_after_bundle_deploy_and_before_app_run():
    lines = (ROOT / "scripts" / "deploy.sh").read_text().splitlines()
    at = lambda needle: next(i for i, l in enumerate(lines) if l.strip().startswith(needle))
    assert at('databricks bundle deploy') < at('bash scripts/push_photos.sh "$SUMMARY"') < at('databricks bundle run geologic')
