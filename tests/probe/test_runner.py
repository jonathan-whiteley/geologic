import json
import re
from datetime import date
from pathlib import Path
from geologic.datagen.reference import SUBJECTS, brand_facts, categories
from geologic.probe.engine import Doc, EngineAnswer
from geologic.probe.runner import ANSWER_SCHEMA, CLAIM_SCHEMA, ProbeContext, probe_one, run_probe

ROUNDUP = "editorial_superbowl_roundup_2024"


class Eng:
    def __init__(self, name, answers): self.name, self._a = name, list(answers)
    def answer(self, prompt):
        x = self._a.pop(0)
        if isinstance(x, Exception): raise x
        return x


class Always:
    """Thread-safe fake engine: the same answer for every prompt."""
    def __init__(self, name, ans): self.name, self.ans = name, ans
    def answer(self, prompt): return self.ans


class JudgeChat:
    """Replies in order; an Exception reply is raised (transport error)."""
    def __init__(self, replies): self.replies, self.calls, self.kwargs = list(replies), [], []
    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        self.calls.append((endpoint, messages)); self.kwargs.append({"usage_context": usage_context})
        x = self.replies.pop(0)
        if isinstance(x, Exception): raise x
        return x


class SameJudge:
    def __init__(self, reply): self.reply = reply
    def complete(self, endpoint, messages, max_tokens=600, usage_context=None): return self.reply


def judge_json(claims):
    return json.dumps({"lce_mentioned": True, "lce_rank": 2, "brands_mentioned": ["Domino's", "Little Caesars"],
                       "sentiment": "neutral", "claims": claims})


PP = {"text": "Party Pack is $24.99.", "subject": "party_pack", "attribute": "price", "stated_value": "$24.99"}
GOOD = judge_json([PP])
P = {"prompt_id": "q201", "prompt_text": "What should I order for a Super Bowl party for 12 people?"}
NOOP = lambda s: None


def ctx(chat, owned=frozenset({"lce_pg_menu"})):
    return ProbeContext(chat, "judge", brand_facts(), categories(), SUBJECTS, owned, date(2026, 10, 21))


def cols(schema):
    return [c.split()[0] for c in schema.split(", ")]


def test_probe_one_tags_claims():
    docs = (Doc(ROUNDUP, "Roundup", "Party Pack is $24.99", False), Doc("lce_pg_menu", "Menu", "Party Pack $29.99", True))
    ans = EngineAnswer(f"Party Pack is $24.99 [{ROUNDUP}].", [ROUNDUP], [ROUNDUP, "lce_pg_menu"], docs)
    chat = JudgeChat([GOOD])
    row, claims = probe_one(P, Eng("Meta AI", [ans]), ctx(chat), "r1", 3, sleep=NOOP)
    assert row["status"] == "ok" and row["retrieved_doc_ids"] == [ROUNDUP, "lce_pg_menu"]
    assert row["cited_doc_ids"] == [ROUNDUP] and row["cites_official"] is False
    assert row["lce_rank"] == 2 and row["accuracy_score"] == 0.0
    assert [(c["tag"], c["fact_id"], c["source_doc_id"]) for c in claims] == [("Outdated", "F13", ROUNDUP)]
    assert claims[0]["answer_id"] == row["answer_id"] and claims[0]["epoch"] == 3 and claims[0]["engine"] == "Meta AI"
    assert "party_pack" in chat.calls[0][1][0]["content"]     # the judge sees the subject vocabulary


def test_probe_one_cites_official():
    ans = EngineAnswer("It is $29.99 [lce_pg_menu].", ["lce_pg_menu"], ["lce_pg_menu"], ())
    row, _ = probe_one(P, Eng("Claude", [ans]), ctx(JudgeChat([judge_json([])])), "r1", 1, sleep=NOOP)
    assert row["cites_official"] is True and row["accuracy_score"] is None


def test_probe_one_engine_error_row():
    slept = []
    row, claims = probe_one(P, Eng("Meta AI", [RuntimeError("429")] * 3), ctx(JudgeChat([])), "r1", 1, sleep=slept.append)
    assert row["status"] == "engine_error" and row["answer"] is None and claims == []
    assert row["retrieved_doc_ids"] == [] and row["cited_doc_ids"] == [] and row["brands_mentioned"] == []
    assert slept == [1, 2]


def test_engine_recovers_after_retry():
    row, _ = probe_one(P, Eng("Meta AI", [RuntimeError("429"), EngineAnswer("ok", [], [])]), ctx(JudgeChat([GOOD])), "r1", 1,
                       sleep=NOOP)
    assert row["status"] == "ok"


def test_judge_strict_retry_then_unjudged():
    ans = EngineAnswer("x", [], ["d1"], (Doc("d1", "t", "b", False),))
    row, claims = probe_one(P, Eng("Gemini", [ans]), ctx(JudgeChat(["garbage", "still garbage"])), "r1", 1, sleep=NOOP)
    assert row["status"] == "unjudged" and row["accuracy_score"] is None and claims == []
    assert row["retrieved_doc_ids"] == ["d1"] and row["answer"] == "x"


def test_judge_strict_retry_succeeds():
    chat = JudgeChat(["garbage", GOOD])
    row, _ = probe_one(P, Eng("Gemini", [EngineAnswer("x", [], [])]), ctx(chat), "r1", 1, sleep=NOOP)
    assert row["status"] == "ok" and "No markdown fences" in chat.calls[1][1][0]["content"]


def test_run_probe_parallel_covers_every_pair():
    prompts = [{"prompt_id": f"q00{i}", "prompt_text": f"p{i}"} for i in range(3)]
    ans = EngineAnswer("Party Pack is $24.99.", [], [], ())
    engines = [Always("Claude", ans), Always("Gemini", ans)]
    answers, claims = run_probe(prompts, engines, ctx(SameJudge(GOOD)), "r1", 1, max_workers=4)
    assert len(answers) == 6 and len({a["answer_id"] for a in answers}) == 6
    assert {(a["prompt_id"], a["engine"]) for a in answers} == {(p["prompt_id"], e.name) for p in prompts for e in engines}
    assert len(claims) == 6 and len({c["claim_id"] for c in claims}) == 6


def test_rows_match_the_write_schemas_and_the_ddl():
    ans = EngineAnswer(f"Party Pack is $24.99 [{ROUNDUP}].", [ROUNDUP], [ROUNDUP], ())
    row, claims = probe_one(P, Eng("Claude", [ans]), ctx(JudgeChat([GOOD])), "r1", 1, sleep=NOOP)
    err, _ = probe_one(P, Eng("Claude", [RuntimeError("x")] * 3), ctx(JudgeChat([])), "r1", 1, sleep=NOOP)
    assert list(row) == cols(ANSWER_SCHEMA) and list(err) == cols(ANSWER_SCHEMA)
    assert sorted(claims[0]) == sorted(cols(CLAIM_SCHEMA))
    ddl = (Path(__file__).resolve().parents[2] / "sql" / "tables.sql").read_text()
    for table, schema in (("probe_responses", ANSWER_SCHEMA), ("claims", CLAIM_SCHEMA)):
        body = re.search(rf"{{{{schema}}}}\.{table} \((.*?)\);", ddl, re.S).group(1)
        assert " ".join(body.split()) == schema


def test_judge_call_carries_usage_context(monkeypatch):
    import geologic.probe.engine as E
    from geologic.config import Settings
    monkeypatch.setattr(E, "settings", Settings(schema="geologic_v3"))
    chat = JudgeChat([GOOD])
    probe_one(P, Eng("Claude", [EngineAnswer("x", [], [])]), ctx(chat), "r1", 1, sleep=NOOP)
    assert chat.kwargs[0]["usage_context"] == {"app": "geologic_v3", "role": "judge"}


def test_probe_one_judge_transport_error_retries_then_unjudged(capsys):
    ans = EngineAnswer("Party Pack is $24.99.", [], ["d1"], (Doc("d1", "t", "b", False),))
    slept = []
    chat = JudgeChat([TimeoutError("judge timed out"), RuntimeError("429"), GOOD])
    row, claims = probe_one(P, Eng("Claude", [ans]), ctx(chat), "r1", 1, sleep=slept.append)
    assert row["status"] == "ok" and len(claims) == 1 and slept == [1, 2]
    chat = JudgeChat([RuntimeError("503")] * 3)
    row, claims = probe_one(P, Eng("Claude", [ans]), ctx(chat), "r1", 1, sleep=NOOP)
    assert row["status"] == "unjudged" and claims == [] and len(chat.calls) == 3
    assert row["answer"] == "Party Pack is $24.99." and row["retrieved_doc_ids"] == ["d1"]
    out = capsys.readouterr().out
    assert "RuntimeError" in out and "q201" in out and "Claude" in out


def test_engine_error_is_logged(capsys):
    probe_one(P, Eng("Gemini", [ConnectionError("reset")] * 3), ctx(JudgeChat([])), "r1", 1, sleep=NOOP)
    out = capsys.readouterr().out
    assert out.count("ConnectionError") == 3 and "q201" in out and "Gemini" in out


class Broken:
    """Returns an answer object that breaks downstream for one prompt (not an engine or judge transport error)."""
    def __init__(self, name, bad_prompt): self.name, self.bad = name, bad_prompt
    def answer(self, prompt):
        return object() if prompt == self.bad else EngineAnswer("Party Pack is $24.99.", [], [], ())


def test_run_probe_one_failure_keeps_other_rows(capsys):
    prompts = [{"prompt_id": f"q00{i}", "prompt_text": f"p{i}"} for i in range(3)]
    answers, claims = run_probe(prompts, [Broken("Claude", "p1"), Always("Gemini", EngineAnswer("ok", [], [], ()))],
                                ctx(SameJudge(GOOD)), "r1", 1, max_workers=4, sleep=NOOP)
    assert len(answers) == 6
    bad = [a for a in answers if a["status"] == "error"]
    assert [(a["prompt_id"], a["engine"]) for a in bad] == [("q001", "Claude")]
    assert list(bad[0]) == cols(ANSWER_SCHEMA) and bad[0]["retrieved_doc_ids"] == []
    assert sum(a["status"] == "ok" for a in answers) == 5 and len(claims) == 5
    out = capsys.readouterr().out
    assert "AttributeError" in out and "q001" in out and "Claude" in out


def test_probe_one_maps_party_pack_display_name_back_to_its_id():
    # Smoke 1 F1: "$24.99 Game Day Party Pack" must tag party_pack Outdated F13, never gameday_499 Wrong vs F06.
    from geologic.datagen.reference import subject_vocabulary
    docs = (Doc(ROUNDUP, "Roundup", "Party Pack is $24.99", False),)
    ans = EngineAnswer(f"The Game Day Party Pack is $24.99 [{ROUNDUP}].", [ROUNDUP], [ROUNDUP], docs)
    chat = JudgeChat([judge_json([{**PP, "subject": "Game Day Party Pack"}])])
    c = ProbeContext(chat, "judge", brand_facts(), categories(), subject_vocabulary(), frozenset(), date(2026, 10, 21))
    _row, claims = probe_one(P, Eng("Claude", [ans]), c, "r1", 1, sleep=NOOP)
    assert [(x["subject"], x["tag"], x["fact_id"]) for x in claims] == [("party_pack", "Outdated", "F13")]
    assert "party_pack: Game Day Party Pack" in chat.calls[0][1][0]["content"]
