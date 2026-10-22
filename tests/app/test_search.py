import sys, pathlib, re, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "app"))
from backend.search import Search, Tracker, SearchUnavailable

class Index:
    def __init__(self, hits=None, boom=False): self.hits, self.boom, self.seen, self.ks = hits or [], boom, [], []
    def nearest(self, text, k=3):
        self.seen.append(text); self.ks.append(k)
        if self.boom: raise RuntimeError("vs down")
        return self.hits[:k]

def test_search_input_edges():  # Review Focus 4
    s = Search(Index(), 0.80, lambda pid: [])
    for bad in ("", "   ", "?!..."):
        with pytest.raises(ValueError):
            s.search(bad)
    idx = Index([]); Search(idx, 0.80, lambda pid: []).search("pizza " * 100)
    assert len(idx.seen[0]) == 200
    with pytest.raises(SearchUnavailable):
        Search(Index(boom=True), 0.80, lambda pid: []).search("pizza")

def test_match_threshold_and_untracked_nearest():
    hits = [{"id": "q201", "prompt_text": "Super Bowl for 12", "kind": "tracked", "cluster": "game_day_party", "score": 0.94}]
    out = Search(Index(hits), 0.80, lambda pid: [{"engine": "Claude"}]).search("what should I order for a super bowl party for 12")
    assert out["match"] == {"prompt_id": "q201", "prompt_text": "Super Bowl for 12", "score": 0.94} and out["scorecard"] == [{"engine": "Claude"}]
    low = [{**hits[0], "score": 0.79}]
    out = Search(Index(low), 0.80, lambda pid: 1 / 0).search("x pizza")
    assert out["match"] is None and out["nearest"]["id"] == "q201" and out["scorecard"] is None
    sug = [{"id": "c004", "prompt_text": "Little Caesars deals today", "kind": "suggested", "cluster": "value", "score": 0.91}]
    assert Search(Index(sug), 0.80, lambda pid: []).search("deals today")["match"] is None

def test_track_generates_safe_id():  # Review Focus 4
    class Reads:
        def __init__(self): self.inserted = []
        def next_prompt_id(self): return "q301"
        def insert_prompt(self, row): self.inserted.append(row)
        def suggestion(self, sid): return None
        def mark_suggestion_tracked(self, sid): pass
    class Store:
        def reask(self, pids): return {(pids[0], "Claude"): {"answer": {"engine": "Claude", "status": "ok", "lce_mentioned": True,
                                                                       "lce_rank": 1, "cited_doc_ids": [], "retrieved_doc_ids": [], "answer": "a"},
                                                            "claims": []}}
    reads, written = Reads(), []
    t = Tracker(reads, lambda: Store(), lambda row, delete=None: written.append((row, delete)), clock=lambda: 0.0,
                nearest=lambda text: {"id": "q062", "cluster": "game_day_party", "kind": "tracked", "score": 0.7})
    out = t.track("Pizza for 15'; DROP TABLE prompts; --", None, "me")
    assert re.fullmatch(r"q3\d{2}", out["prompt_id"]) and reads.inserted[0]["prompt_text"].startswith("Pizza for 15'")
    assert reads.inserted[0]["cluster"] == "game_day_party" and reads.inserted[0]["priority"] == "Bronze"
    assert written[0][0]["kind"] == "tracked" and out["scorecard"][0]["engine"] == "Claude"
    with pytest.raises(ValueError):
        t.track("??", None, "me")

def test_track_refuses_an_id_outside_q3xx():
    class Reads:
        def next_prompt_id(self): return "q400"
    with pytest.raises(ValueError, match="limit"):
        Tracker(Reads(), None, None, clock=lambda: 0.0, nearest=None).track("pizza for 20", None, "me")


class TrackReads:
    def __init__(self): self.inserted, self.deleted, self.marked = [], [], []
    def next_prompt_id(self): return "q301"
    def insert_prompt(self, row): self.inserted.append(row)
    def delete_prompt(self, pid): self.deleted.append(pid)
    def suggestion(self, sid): return {"cluster": "value"}
    def mark_suggestion_tracked(self, sid): self.marked.append(sid)


def test_track_fails_before_any_write_when_embedding_is_down():   # fix round 1
    reads = TrackReads()
    def down(text): raise RuntimeError("embeddings down")
    t = Tracker(reads, None, None, clock=lambda: 0.0, nearest=down)
    with pytest.raises(SearchUnavailable):
        t.track("pizza for 20 people", "c004", "me")
    assert reads.inserted == [] and reads.marked == []


def test_track_rolls_back_the_prompt_when_the_reask_or_index_fails():   # fix round 1
    near = lambda text: {"cluster": "game_day_party"}
    class Down:
        def reask(self, pids): raise RuntimeError("gateway down")
    reads = TrackReads()
    with pytest.raises(SearchUnavailable):
        Tracker(reads, lambda: Down(), lambda row, delete=None: None, clock=lambda: 0.0, nearest=near).track("pizza for 20", "c004", "me")
    assert reads.inserted[0]["cluster"] == "value" and reads.deleted == ["q301"] and reads.marked == []
    class Up:
        def reask(self, pids): return {}
    def no_index(row, delete=None): raise RuntimeError("vs down")
    reads = TrackReads()
    with pytest.raises(SearchUnavailable):
        Tracker(reads, lambda: Up(), no_index, clock=lambda: 0.0, nearest=near).track("pizza for 20", None, "me")
    assert reads.deleted == ["q301"]


def test_search_reads_five_and_prefers_the_best_tracked_prompt_over_suggestions():   # final review M9
    hit = lambda i, kind, score: {"id": i, "prompt_text": i, "kind": kind, "cluster": "value", "score": score}
    hits = [hit("c004", "suggested", 0.95), hit("c005", "suggested", 0.93), hit("c006", "suggested", 0.92),
            hit("q002", "tracked", 0.84), hit("q007", "tracked", 0.88)]
    idx = Index(hits)
    out = Search(idx, 0.80, lambda pid: [pid]).search("little caesars deals today")
    assert idx.ks == [5] and out["match"]["prompt_id"] == "q007" and out["scorecard"] == ["q007"]
    assert out["nearest"]["id"] == "c004"
    at = Search(Index([hit("q002", "tracked", 0.80)]), 0.80, lambda pid: []).search("deals")
    assert at["match"]["prompt_id"] == "q002"   # at the threshold counts
