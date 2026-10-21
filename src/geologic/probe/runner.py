"""Runs prompts across engines, judges answers and tags claims. Used by the probe job and the targeted re-ask."""
from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from geologic.claims import accuracy, answer_id, claim_rows
from geologic.probe.engine import usage_context
from geologic.probe.judge import JudgeParseError, judge_messages, parse_judge_output

# Write schemas for probe_responses and claims (same columns as sql/tables.sql). Task 9 reuses them for warehouse inserts.
ANSWER_SCHEMA = ("answer_id STRING, run_id STRING, epoch INT, prompt_id STRING, engine STRING, status STRING, answer STRING, "
                 "retrieved_doc_ids ARRAY<STRING>, cited_doc_ids ARRAY<STRING>, cites_official BOOLEAN, lce_mentioned BOOLEAN, "
                 "lce_rank INT, brands_mentioned ARRAY<STRING>, sentiment STRING, accuracy_score DOUBLE")
CLAIM_SCHEMA = ("claim_id STRING, answer_id STRING, run_id STRING, epoch INT, prompt_id STRING, engine STRING, text STRING, "
                "subject STRING, attribute STRING, stated_value STRING, tag STRING, fact_id STRING, source_doc_id STRING")


@dataclass(frozen=True)
class ProbeContext:
    chat: object
    judge_endpoint: str
    facts: list
    categories: dict
    subjects: tuple
    owned_ids: frozenset
    today: object


def _answer_row(run_id, epoch, prompt_id, engine, status, ans=None, j=None, acc=None, owned=frozenset()):
    return dict(answer_id=answer_id(run_id, prompt_id, engine), run_id=run_id, epoch=epoch, prompt_id=prompt_id, engine=engine,
                status=status, answer=ans.answer if ans else None,
                retrieved_doc_ids=list(ans.retrieved_doc_ids) if ans else [], cited_doc_ids=list(ans.cited_doc_ids) if ans else [],
                cites_official=bool(ans and any(d in owned for d in ans.cited_doc_ids)),
                lce_mentioned=j.lce_mentioned if j else None, lce_rank=j.lce_rank if j else None,
                brands_mentioned=j.brands_mentioned if j else [], sentiment=j.sentiment if j else None, accuracy_score=acc)


def _log(what, e, prompt_id, engine):
    print(f"probe: {what} {type(e).__name__} prompt={prompt_id} engine={engine}: {str(e)[:200]}", flush=True)


def _judge(prompt, ans, engine_name, ctx: ProbeContext, max_retries, sleep):
    """Judge an answer. Transport errors (429, timeout, 5xx) get a bounded retry with backoff; an unparseable reply gets
    one strict re-ask. Returns None when either is exhausted (the answer row becomes unjudged)."""
    for strict in (False, True):
        messages, raw = judge_messages(prompt["prompt_text"], ans.answer, strict, ctx.subjects), None
        for attempt in range(max_retries + 1):
            try:
                raw = ctx.chat.complete(ctx.judge_endpoint, messages, usage_context=usage_context("judge"))
                break
            except Exception as e:
                _log("judge call", e, prompt["prompt_id"], engine_name)
                if attempt < max_retries:
                    sleep(2 ** attempt)
        if raw is None:
            return None
        try:
            return parse_judge_output(raw, ctx.subjects)
        except JudgeParseError as e:
            _log("judge parse", e, prompt["prompt_id"], engine_name)
    return None


def probe_one(prompt, engine, ctx: ProbeContext, run_id, epoch, max_retries=2, sleep=time.sleep):
    ans = None
    for attempt in range(max_retries + 1):
        try:
            ans = engine.answer(prompt["prompt_text"])
            break
        except Exception as e:
            _log("engine call", e, prompt["prompt_id"], engine.name)
            if attempt < max_retries:
                sleep(2 ** attempt)
    if ans is None:
        return _answer_row(run_id, epoch, prompt["prompt_id"], engine.name, "engine_error"), []
    j = _judge(prompt, ans, engine.name, ctx, max_retries, sleep)
    if j is None:
        return _answer_row(run_id, epoch, prompt["prompt_id"], engine.name, "unjudged", ans, owned=ctx.owned_ids), []
    aid = answer_id(run_id, prompt["prompt_id"], engine.name)
    meta = {"run_id": run_id, "epoch": epoch, "prompt_id": prompt["prompt_id"], "engine": engine.name}
    claims = claim_rows(aid, meta, j.claims, ctx.facts, ans.docs, ans.answer, ctx.today, ctx.categories)
    return _answer_row(run_id, epoch, prompt["prompt_id"], engine.name, "ok", ans, j, accuracy(claims), ctx.owned_ids), claims


def run_probe(prompts, engines, ctx, run_id, epoch, max_workers=8, sleep=time.sleep):
    def one(pe):
        p, e = pe
        try:
            return probe_one(p, e, ctx, run_id, epoch, sleep=sleep)
        except Exception as ex:   # last resort: one bad pair never loses the rest of the run
            _log("unexpected", ex, p.get("prompt_id"), getattr(e, "name", None))
            return _answer_row(run_id, epoch, p.get("prompt_id"), getattr(e, "name", None), "error"), []

    pairs = [(p, e) for p in prompts for e in engines]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        out = list(pool.map(one, pairs))
    return [a for a, _ in out], [c for _, cs in out for c in cs]
