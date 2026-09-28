import json
from geologic.datagen.reference import menu_items, deals
from geologic.probe.engine import EngineAnswer
from geologic.probe.runner import run_probe

class Eng:
    def __init__(self, name, answers): self.name, self._a = name, list(answers)
    def answer(self, prompt):
        x = self._a.pop(0)
        if isinstance(x, Exception): raise x
        return x

class JudgeChat:
    def __init__(self, replies): self.replies = list(replies)
    def complete(self, endpoint, messages, max_tokens=600): return self.replies.pop(0)

GOOD = json.dumps({"lce_mentioned": True, "lce_rank": 2, "brands_mentioned": ["Domino's", "Little Caesars"],
                   "sentiment": "neutral", "claims": [{"item": "Hot-N-Ready", "price": "$5"}]})
P = [{"prompt_id": "q001", "prompt_text": "price?"}]

def run(engines, judge):
    return run_probe(P, engines, JudgeChat(judge), "judge", menu_items(), deals(), "r1", 1, {"lce_pg_x"}, sleep=lambda s: None)

def test_ok_row():
    rows = run([Eng("Claude", [EngineAnswer("It's $5", ["lce_pg_x"], ["lce_pg_x"])])], [GOOD])
    r = rows[0]
    assert r["status"] == "ok" and r["lce_rank"] == 2 and r["cites_official"] is True
    assert r["accuracy_score"] == 0.0 and r["claims"][0]["verdict"] == "wrong"

def test_engine_retries_then_error():
    rows = run([Eng("Llama", [RuntimeError("429")] * 3)], [])
    assert rows[0]["status"] == "engine_error" and rows[0]["answer"] is None

def test_engine_recovers_after_retry():
    rows = run([Eng("Llama", [RuntimeError("429"), EngineAnswer("ok", [], [])])], [GOOD])
    assert rows[0]["status"] == "ok"

def test_judge_strict_retry_then_unjudged():
    rows = run([Eng("Gemma", [EngineAnswer("x", [], [])])], ["garbage", "still garbage"])
    assert rows[0]["status"] == "unjudged" and rows[0]["accuracy_score"] is None

def test_judge_strict_retry_succeeds():
    rows = run([Eng("Gemma", [EngineAnswer("x", [], [])])], ["garbage", GOOD])
    assert rows[0]["status"] == "ok"
