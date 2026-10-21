"""Rehearse approve to ledger on the live v3 app: approve the Party Pack owned patch, time it to the ledger, Reset, repeat.

Usage:
  python3 scripts/rehearse.py --target v3 [--runs 5] [--fix FIX_ID]

The app URL comes from `databricks apps get geologic-v3`, the bearer token from `databricks auth token` (profile DEFAULT).
Only the app geologic-v3 is accepted. Per run: POST /api/fixes/<id>/approve, poll /api/fixes/<id>/status every 2 s until
`published` (gives up at 120 s), confirm /api/impact has a ledger entry for the fix under the current epoch, record the
seconds, then POST /api/demo/reset and wait for TERMINATED / SUCCESS. Exits 1 unless every run passes.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROFILE = "DEFAULT"
APPS = {"v3": "geologic-v3"}
POLL_S, GIVE_UP_S, RESET_GIVE_UP_S = 2.0, 120.0, 900.0


def summarize_runs(times: list[float | None], limit: float = 60.0) -> tuple[bool, str]:
    """Pass only when every run finished and every time is under the limit."""
    n = len(times)
    good = sum(1 for t in times if t is not None and t < limit)
    shown = ", ".join("failed" if t is None else f"{t:.1f} s" for t in times)
    ok = n > 0 and good == n
    if ok:
        return True, f"{good} of {n} under {limit:g} s ({shown})"
    return False, f"{n - good} of {n} failed or not under {limit:g} s ({shown})"


def app_problem(name: str) -> str | None:
    return None if name == "geologic-v3" else f"refusing app {name!r}: only geologic-v3 may be rehearsed"


def pick_fix(fixes: list[dict], fix_id: str | None = None) -> str | None:
    """The requested fix, or the Party Pack owned patch (owned_patch on an outdated issue about the Party Pack)."""
    if fix_id:
        return fix_id if any(f.get("fix_id") == fix_id for f in fixes) else None
    for f in fixes:
        if f.get("asset_type") == "owned_patch" and f.get("issue_type") == "outdated" and "Party Pack" in (f.get("title") or ""):
            return f["fix_id"]
    return None


def _cli(*args: str) -> dict:
    out = subprocess.run(["databricks", *args, "--profile", PROFILE, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"databricks {' '.join(args[:2])} failed: {out.stderr.strip() or out.stdout.strip()}")
    return json.loads(out.stdout or "{}")


class Api:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._token, self._at = None, 0.0

    def token(self) -> str:
        if self._token is None or time.time() - self._at > 600:
            self._token, self._at = _cli("auth", "token")["access_token"], time.time()
        return self._token

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
        req = urllib.request.Request(self.url + "/api" + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"null")
            except ValueError:
                return e.code, None


def wait_reset(api: Api) -> bool:
    st, body = api.call("POST", "/demo/reset")
    if st != 202:
        print(f"  reset: POST returned {st} {body}")
        return False
    run_id, t0 = body["run_id"], time.time()
    while time.time() - t0 < RESET_GIVE_UP_S:
        time.sleep(5)
        st, s = api.call("GET", f"/demo/reset/{run_id}")
        if st == 200 and s.get("life_cycle_state") in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
            ok = s.get("life_cycle_state") == "TERMINATED" and s.get("result_state") == "SUCCESS"
            print(f"  reset run {run_id}: {s.get('life_cycle_state')} {s.get('result_state')} in {time.time() - t0:.0f} s")
            return ok
    print(f"  reset run {run_id}: gave up after {RESET_GIVE_UP_S:.0f} s")
    return False


def one_run(api: Api, fix_id: str) -> float | None:
    t0 = time.time()
    st, body = api.call("POST", f"/fixes/{fix_id}/approve")
    if st != 202:
        print(f"  approve: {st} {body}")
        return None
    state = None
    while time.time() - t0 < GIVE_UP_S:
        time.sleep(POLL_S)
        st, s = api.call("GET", f"/fixes/{fix_id}/status")
        if st != 200:
            continue
        state = s.get("state")
        if state == "published":
            break
        if state != "publishing":
            print(f"  status: {state} {s.get('error')}")
            return None
    if state != "published":
        print(f"  status: gave up after {GIVE_UP_S:.0f} s (state {state})")
        return None
    st, imp = api.call("GET", "/impact")
    ledger = (imp or {}).get("ledger") or []
    entry = next((e for e in ledger if e.get("fix_id") == fix_id and not e.get("rehearsal")), None)
    secs = time.time() - t0
    if entry is None:
        print(f"  impact: no current-epoch ledger entry for {fix_id}")
        return None
    print(f"  ledger: epoch {entry.get('epoch')}, {entry.get('engines_answered')} of {entry.get('engines_total')} engines, "
          f"server elapsed {entry.get('elapsed_s')}")
    return secs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, choices=sorted(APPS))
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--fix")
    a = ap.parse_args(argv)
    name = APPS[a.target]
    problem = app_problem(name)
    if problem:
        print(problem)
        return 1
    app = _cli("apps", "get", name)
    problem = app_problem(app.get("name", ""))
    if problem or not app.get("url"):
        print(problem or f"app {name} has no url")
        return 1
    api = Api(app["url"])
    st, fixes = api.call("GET", "/fixes")
    if st != 200:
        print(f"GET /api/fixes returned {st}")
        return 1
    fix_id = pick_fix(fixes, a.fix)
    if not fix_id:
        print("no Party Pack owned patch found" if not a.fix else f"unknown fix {a.fix}")
        return 1
    print(f"rehearsing {fix_id} on {app['url']} ({a.runs} runs)")
    times: list[float | None] = []
    for i in range(1, a.runs + 1):
        print(f"run {i}: {time.strftime('%H:%M:%S')}")
        t = one_run(api, fix_id)
        times.append(t)
        print(f"  approve to ledger: {'failed' if t is None else f'{t:.1f} s'}")
        if not wait_reset(api):
            print("  reset failed; stopping")
            break
    print("\n run | seconds")
    for i, t in enumerate(times, 1):
        print(f" {i:>3} | {'failed' if t is None else f'{t:.1f}'}")
    ok, msg = summarize_runs(times + [None] * (a.runs - len(times)))
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
