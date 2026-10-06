from geologic.datagen.reference import exclusion_rules
from geologic.publish_flow import publish, reset, FRIENDLY_ERROR

class FakeStore:
    def __init__(self, epoch=1):
        self.pages = {"p": {"page_id": "p", "body": "old", "jsonld": None, "version": 1}}
        self.states, self.audits, self.reprobed, self.synced, self.versions, self.epoch = {}, [], [], 0, [], epoch
        self.fail_write, self.steps = False, []
    def get_page(self, pid): return dict(self.pages[pid])
    def write_page(self, page):
        if self.fail_write: raise RuntimeError("disk")
        self.pages[page["page_id"]] = page
    def record_version(self, page, by): self.versions.append((page["page_id"], page["version"], by))
    def set_state(self, sid, state, error=None):  # scoped like DeltaStore: only rows still 'publishing'
        if self.states.get(sid, ("publishing",))[0] == "publishing": self.states[sid] = (state, error)
    def set_step(self, sid, n): self.steps.append(n)
    def audit(self, *a): self.audits.append(a)
    def sync_index(self): self.synced += 1
    def reprobe(self, ids): self.reprobed.append(ids)
    def current_epoch(self): return self.epoch

RULES = exclusion_rules()
SG = {"suggestion_id": "s1", "page_id": "p", "asset_type": "faq", "diff_after": "new $6.49", "tier": "T1",
      "state": "approved", "epoch": 1, "persona_id": None, "prompt_ids": ["q001"]}

def test_publish_happy_path():
    st = FakeStore()
    assert publish(SG, st, RULES, 1) == "published"
    assert st.pages["p"]["version"] == 2 and st.states["s1"][0] == "published"
    assert st.synced == 1 and st.reprobed == [["q001"]] and st.versions == [("p", 2, "s1")]
    assert st.steps == [1, 2, 3, 5]

def test_publish_recheck_blocks_exclusion():
    st = FakeStore()
    assert publish({**SG, "diff_after": "Dax Merriwether deal", "persona_id": "p_fictional_dax"}, st, RULES, 1) == "blocked"
    assert st.pages["p"]["version"] == 1 and st.audits[-1][3:] == ("EX-01", "publish")

def test_publish_stale_epoch_is_refused():  # Review Focus 4
    st = FakeStore(epoch=2)
    assert publish(SG, st, RULES, 1) == "stale" and st.pages["p"]["version"] == 1

def test_publish_failure_keeps_version_and_reports():
    st = FakeStore(); st.fail_write = True
    assert publish(SG, st, RULES, 1) == "failed"
    assert st.pages["p"]["version"] == 1 and st.states["s1"] == ("pending_review", FRIENDLY_ERROR)

def test_publish_is_idempotent_for_already_applied_content():
    """Drafting calls publish for T0 rows on every run; a repeat must not bump the version."""
    st = FakeStore()
    t0 = {**SG, "tier": "T0", "state": "auto_published", "prompt_ids": []}
    assert publish(t0, st, RULES, 1, reprobe=False) == "published"
    assert st.pages["p"]["version"] == 2 and st.synced == 1
    assert publish(t0, st, RULES, 1, reprobe=False) == "published"
    assert st.pages["p"]["version"] == 2 and st.versions == [("p", 2, "s1")] and st.synced == 1
    assert st.states["s1"][0] == "auto_published"

def test_publish_idempotent_jsonld():
    st = FakeStore(); st.pages["p"]["jsonld"] = "{}"
    sg = {**SG, "asset_type": "jsonld", "diff_after": "{}", "tier": "T0", "state": "auto_published", "prompt_ids": []}
    assert publish(sg, st, RULES, 1, reprobe=False) == "published" and st.pages["p"]["version"] == 1

def test_publish_epoch_changes_before_write_is_refused():
    st = FakeStore()
    orig = st.set_step
    def bump(sid, n):
        orig(sid, n)
        if n == 1: st.epoch = 2  # reset lands after the entry check
    st.set_step = bump
    assert publish(SG, st, RULES, 1) == "stale"
    assert st.pages["p"]["version"] == 1 and st.versions == [] and st.synced == 0
    assert st.states["s1"] == ("pending_review", FRIENDLY_ERROR)

def test_publish_epoch_changes_during_sync_does_not_mark_published():
    st = FakeStore()
    st.sync_index = lambda: setattr(st, "epoch", 2)
    assert publish(SG, st, RULES, 1) == "stale"
    assert st.states["s1"][0] == "pending_review"

def test_retry_after_failed_sync_still_syncs_and_reprobes():
    st = FakeStore()
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] == 1: raise RuntimeError("vs down")
        st.synced += 1
    st.sync_index = flaky
    assert publish(SG, st, RULES, 1) == "failed"
    assert st.pages["p"]["version"] == 2 and st.states["s1"] == ("pending_review", FRIENDLY_ERROR)
    st.states["s1"] = ("publishing", None)  # Approve again: claim() moves it back to publishing
    assert publish({**SG, "state": "publishing"}, st, RULES, 1) == "published"
    assert st.pages["p"]["version"] == 2 and st.versions == [("p", 2, "s1")]
    assert st.synced == 1 and st.reprobed == [["q001"]] and st.states["s1"] == ("published", None)

def test_stale_publish_never_touches_a_restored_row():
    st = FakeStore()
    st.states["s1"] = ("publishing", None)
    def reset_lands(sid, n):
        if n == 1:
            st.epoch = 2
            st.states["s1"] = ("pending_review", None)  # reset restored the row under the new epoch
    st.set_step = reset_lands
    assert publish(SG, st, RULES, 1) == "stale"
    assert st.states["s1"] == ("pending_review", None) and st.pages["p"]["version"] == 1

class FakeReset:
    def __init__(self): self.calls, self.e = [], 1
    def bump_epoch(self): self.e += 1; self.calls.append("bump"); return self.e
    def restore_pages(self): self.calls.append("pages")
    def clear_suggestions(self): self.calls.append("clear")
    def restore_suggestions(self, epoch): self.calls.append(f"sugg{epoch}")
    def copy_baseline_probe(self, epoch): self.calls.append(f"probe{epoch}")
    def sync_index(self): self.calls.append("sync")

def test_reset_bumps_epoch_first():
    r = FakeReset()
    assert reset(r) == 2
    assert r.calls == ["bump", "clear", "sugg2", "probe2", "pages", "sync"]  # slow index sync last

def test_failure_logs_raw_error_but_card_gets_friendly_text(capsys):
    st = FakeStore(); st.fail_write = True
    st.states["s1"] = ("publishing", None)
    assert publish(SG, st, RULES, 1) == "failed"
    assert st.states["s1"] == ("pending_review", FRIENDLY_ERROR) and "disk" in capsys.readouterr().out

def test_stale_entry_returns_row_to_review():
    st = FakeStore(epoch=2); st.states["s1"] = ("publishing", None)
    assert publish(SG, st, RULES, 1) == "stale" and st.states["s1"] == ("pending_review", FRIENDLY_ERROR)

def test_final_state_never_overwrites_a_row_no_longer_publishing():  # finding 9
    st = FakeStore(); st.states["s1"] = ("publishing", None)
    st.reprobe = lambda ids: st.states.__setitem__("s1", ("rejected", None))
    assert publish(SG, st, RULES, 1) == "published" and st.states["s1"] == ("rejected", None)
