"""'Ask anything' (match free text to a tracked prompt in prompt_idx) and 'Track and run now' (a new tracked prompt, asked
on every engine). User text never reaches SQL: new prompt ids are generated server side and all values go as parameters."""
import re
from geologic.datagen.reference import is_branded

ENGINE_ORDER = ("Claude", "ChatGPT", "Gemini", "Meta AI")
MAX_CHARS = 200
SEARCH_K = 5   # suggestions share prompt_idx: read past them so a tracked prompt at or above threshold still matches
_NEW_ID = re.compile(r"^q3\d{2}$")


class SearchUnavailable(RuntimeError):
    pass


def normalize(text):
    return " ".join((text or "").split())[:MAX_CHARS].strip()


class Search:
    def __init__(self, index, threshold, scorecard_fn):
        self.index, self.threshold, self.scorecard_fn = index, threshold, scorecard_fn

    def search(self, q):
        text = normalize(q)
        if not re.search(r"[A-Za-z0-9]", text):
            raise ValueError("Type a question to search.")
        try:
            hits = list(self.index.nearest(text, SEARCH_K) or [])
        except Exception as e:
            print(f"search: {type(e).__name__}: {e}")
            raise SearchUnavailable("Search is unavailable right now.") from e
        # The best tracked prompt at or above threshold wins, even when suggestions score higher.
        tracked = [h for h in hits if h.get("kind") == "tracked" and h["score"] >= self.threshold]
        best = max(tracked, key=lambda h: h["score"]) if tracked else None
        match = {"prompt_id": best["id"], "prompt_text": best["prompt_text"], "score": best["score"]} if best else None
        nearest = {k: hits[0][k] for k in ("id", "prompt_text", "kind", "score")} if hits else None
        return {"query": text, "threshold": self.threshold, "match": match, "nearest": nearest,
                "scorecard": self.scorecard_fn(best["id"]) if best else None}


def scorecard_from(answer_map, prompt_id):
    """AnswerT rows for one prompt from a re-ask map, in engine order. Cited chips come from the store when it attached them."""
    rows = [v for (p, _e), v in answer_map.items() if p == prompt_id]
    rows.sort(key=lambda v: ENGINE_ORDER.index(v["answer"]["engine"]) if v["answer"]["engine"] in ENGINE_ORDER else 99)
    out = []
    for v in rows:
        a = v["answer"]
        cited = a.get("cited") or [{"doc_id": d, "domain": None, "owner_class": "Owned" if str(d).startswith("lce_") else None,
                                    "title": d, "url": None, "last_updated": None} for d in a.get("cited_doc_ids") or []]
        out.append({"engine": a["engine"], "status": a.get("status"), "answer": a.get("answer"), "lce_mentioned": a.get("lce_mentioned"),
                    "lce_rank": a.get("lce_rank"), "cited": cited,
                    "owned_retrieved": any(str(d).startswith("lce_") for d in a.get("retrieved_doc_ids") or []),
                    "claims": [{"claim_id": c.get("claim_id"), "text": c.get("text"), "subject": c.get("subject"),
                                "attribute": c.get("attribute"), "stated_value": c.get("stated_value"), "tag": c.get("tag"),
                                "fact_id": c.get("fact_id"), "source_doc_id": c.get("source_doc_id"), "issue_id": None}
                               for c in v.get("claims") or []]})
    return out


class Tracker:
    def __init__(self, reads, store_factory, index_writer, clock, nearest):
        self.reads, self.store_factory, self.index_writer, self.clock, self.nearest = reads, store_factory, index_writer, clock, nearest

    def track(self, text, suggestion_id, user):
        text = normalize(text)
        if len(text) < 3 or not re.search(r"[A-Za-z]", text):
            raise ValueError("Type a question to track.")
        start = self.clock()
        prompt_id = self.reads.next_prompt_id()
        if not _NEW_ID.match(prompt_id or ""):
            raise ValueError("Tracked prompt limit reached.")
        sug = self.reads.suggestion(suggestion_id) if suggestion_id else None
        try:   # embed first: Vector Search or the embedding endpoint being down fails before any write
            near = self.nearest(text)
        except Exception as e:
            print(f"track: nearest failed: {type(e).__name__}: {e}")
            raise SearchUnavailable("Search is unavailable right now.") from e
        cluster = (sug or {}).get("cluster") or (near or {}).get("cluster") or "product"
        self.reads.insert_prompt({"prompt_id": prompt_id, "prompt_text": text, "cluster": cluster, "priority": "Bronze",
                                  "branded": is_branded(text), "base_volume": 300, "calendar_tags": [], "source": "tracked",
                                  "tracked_by": user})
        try:   # the re-ask reads the new prompts row; the vector goes in only once the answers exist
            answers = self.store_factory().reask([prompt_id])
            self.index_writer({"prompt_id": prompt_id, "prompt_text": text, "kind": "tracked", "cluster": cluster}, delete=suggestion_id)
        except Exception as e:
            print(f"track {prompt_id} failed: {type(e).__name__}: {e}; removing the prompt")
            try:
                self.reads.delete_prompt(prompt_id)
            except Exception as e2:
                print(f"track {prompt_id}: could not remove the prompt: {type(e2).__name__}: {e2}")
            raise SearchUnavailable("Search is unavailable right now.") from e
        if suggestion_id:
            self.reads.mark_suggestion_tracked(suggestion_id)
        return {"prompt_id": prompt_id, "prompt_text": text, "scorecard": scorecard_from(answers, prompt_id),
                "elapsed_s": round(self.clock() - start, 1)}
