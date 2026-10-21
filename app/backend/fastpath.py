"""Approve → patch → upsert → re-ask in the app process (spec 5.6), so the proof skips job cold start."""
import threading
from geologic.publish_flow import FRIENDLY_ERROR, publish_fix


class FastPublisher:
    def __init__(self, repo, store_factory, rules_fn, focus_fn, clock, spawn=None):
        self.repo, self.store_factory, self.rules_fn, self.focus_fn, self.clock = repo, store_factory, rules_fn, focus_fn, clock
        self.spawn = spawn or (lambda f: threading.Thread(target=f, daemon=True).start())

    def start(self, fix_id):
        self.spawn(lambda: self._run(fix_id))

    def _run(self, fix_id):
        try:
            fix = self.repo.get(fix_id)
            now = self.clock()
            out = publish_fix(fix, self.store_factory(), self.rules_fn(), now=now, clock=self.clock, focus=self.focus_fn(fix["issue_id"]))
            print(f"fast publish {fix_id}: {out} in {(self.clock() - now).total_seconds():.1f}s")
        except Exception as e:  # anything before publish_fix's own guard: never leave the row 'publishing'
            print(f"fast publish {fix_id} failed: {type(e).__name__}: {e}")
            self.repo.release(fix_id, FRIENDLY_ERROR)
