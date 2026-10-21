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
