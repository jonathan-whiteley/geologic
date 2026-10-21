"""The targeted re-ask: the issue's prompts times every engine, in parallel through AI Gateway. Used by the publish job and
the app backend (no job cold start)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from geologic.clients import DvaRetriever
from geologic.datagen.reference import categories, subject_vocabulary
from geologic.probe.engine import EngineProxy
from geologic.probe.runner import ProbeContext, run_probe


def make_context(chat, judge_endpoint, facts, owned_ids, today):
    # The judge reads subjects as "id: display name (aliases)", like jobs/run_probe.py (smoke 1 F1).
    return ProbeContext(chat, judge_endpoint, facts, categories(), subject_vocabulary(), frozenset(owned_ids), today)


def make_engines(w, chat, embedder, index_name, engines):
    retriever = DvaRetriever(w, index_name, embedder)
    return [EngineProxy(name, ep, retriever, chat) for name, ep in engines.items()]


def reask(prompts, engines, ctx, epoch, trigger, max_workers=16, clock=lambda: datetime.now(timezone.utc)):
    started = clock()
    run_id = f"run_{started:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    answers, claims = run_probe(prompts, engines, ctx, run_id, epoch, max_workers=max_workers)
    run = {"run_id": run_id, "epoch": epoch, "run_type": "targeted", "trigger": trigger, "prompt_ids": [p["prompt_id"] for p in prompts],
           "started_at": started, "finished_at": clock(), "status": "ok"}
    return run, answers, claims


def answer_map(answers, claims, prompt_texts=None):
    """{(prompt_id, engine): {"answer": answer_row (+ prompt_text), "claims": [claim rows of that answer]}}."""
    by_answer = {}
    for c in claims:
        by_answer.setdefault(c["answer_id"], []).append(c)
    return {(a["prompt_id"], a["engine"]): {"answer": {**a, "prompt_text": (prompt_texts or {}).get(a["prompt_id"])},
                                            "claims": by_answer.get(a["answer_id"], [])} for a in answers}
