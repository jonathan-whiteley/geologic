"""Runs prompts across engines, judges answers, and returns probe_responses rows."""
from __future__ import annotations
import time
from geologic.facts import accuracy_score, verify_claims
from geologic.probe.judge import JudgeParseError, judge_messages, parse_judge_output

def _row(run_id, epoch, prompt_id, engine, status, answer=None, cited=None, official=False, j=None, claims=None, acc=None):
    return dict(run_id=run_id, epoch=epoch, prompt_id=prompt_id, engine=engine, status=status, answer=answer,
                cited_doc_ids=cited or [], cites_official=official,
                lce_mentioned=j.lce_mentioned if j else None, lce_rank=j.lce_rank if j else None,
                brands_mentioned=j.brands_mentioned if j else [], sentiment=j.sentiment if j else None,
                claims=claims or [], accuracy_score=acc)

def run_probe(prompts, engines, chat, judge_endpoint, menu, deals, run_id, epoch, official_doc_ids,
              max_retries: int = 2, sleep=time.sleep) -> list[dict]:
    rows = []
    for p in prompts:
        for eng in engines:
            ans = None
            for attempt in range(max_retries + 1):
                try:
                    ans = eng.answer(p["prompt_text"])
                    break
                except Exception:
                    if attempt < max_retries:
                        sleep(2 ** attempt)
            if ans is None:
                rows.append(_row(run_id, epoch, p["prompt_id"], eng.name, "engine_error"))
                continue
            j = None
            for strict in (False, True):
                try:
                    j = parse_judge_output(chat.complete(judge_endpoint, judge_messages(p["prompt_text"], ans.answer, strict)))
                    break
                except JudgeParseError:
                    continue
            official = any(d in official_doc_ids for d in ans.cited_doc_ids)
            if j is None:
                rows.append(_row(run_id, epoch, p["prompt_id"], eng.name, "unjudged", ans.answer, ans.cited_doc_ids, official))
                continue
            checked = verify_claims(j.claims, menu, deals)
            rows.append(_row(run_id, epoch, p["prompt_id"], eng.name, "ok", ans.answer, ans.cited_doc_ids, official,
                             j, checked, accuracy_score(checked)))
    return rows
