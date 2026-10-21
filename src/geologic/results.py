"""Before and after for each (fix, target prompt, engine): what the Impact ledger shows. Owned doc ids start with lce_."""
from __future__ import annotations
ENGINE_ORDER = ("Claude", "ChatGPT", "Gemini", "Meta AI")
TAG_SEVERITY = ("Wrong", "Outdated", "Unverifiable", "Correct")
_SIDES = ("mentioned", "owned_cited", "owned_retrieved", "position", "answer", "cited")
# Lakebase fix_results columns, in DDL order (sql/lakebase_schema.sql); results_rows produces exactly these keys.
RESULT_COLUMNS = ("fix_id", "prompt_id", "engine", "epoch", "issue_id", "title", "tier", "asset_type", "reviewer", "approved_at",
                  "measured_at", "elapsed_s", "prompt_text", "status", "before_mentioned", "after_mentioned", "before_owned_cited",
                  "after_owned_cited", "before_owned_retrieved", "after_owned_retrieved", "before_position", "after_position",
                  "before_claim_tags", "after_claim_tags", "before_answer", "after_answer", "before_cited", "after_cited")
_KEY = ("fix_id", "prompt_id", "engine")
UPSERT_RESULT = (f"INSERT INTO fix_results ({', '.join(RESULT_COLUMNS)}) VALUES ({', '.join(['%s'] * len(RESULT_COLUMNS))}) "
                 "ON CONFLICT (fix_id, prompt_id, engine) DO UPDATE SET "
                 + ", ".join(f"{c} = EXCLUDED.{c}" for c in RESULT_COLUMNS if c not in _KEY))


def result_values(row):
    return tuple(row.get(c) for c in RESULT_COLUMNS)


def _owned(ids):
    return any(str(d).startswith("lce_") for d in ids or [])


def snapshot(answer, claims, focus=None):
    ok = bool(answer) and answer.get("status") == "ok"
    tags = sorted({c["tag"] for c in claims if focus is None or (c.get("subject"), c.get("attribute")) == tuple(focus)},
                  key=TAG_SEVERITY.index)
    return {"ok": ok, "mentioned": bool(answer.get("lce_mentioned")) if ok else None,
            "owned_cited": _owned(answer.get("cited_doc_ids")) if ok else None,
            "owned_retrieved": _owned(answer.get("retrieved_doc_ids")) if ok else None,
            "position": answer.get("lce_rank") if ok else None, "tags": tags, "tag": tags[0] if tags else None,
            "answer": (answer or {}).get("answer"), "cited": list((answer or {}).get("cited_doc_ids") or [])}


def results_rows(fix, before, after, *, now, approved_at=None, elapsed_s=None, prompt_texts=None, focus=None):
    rows = []
    for pid in fix["prompt_ids"]:
        engines = sorted({e for (p, e) in list(before) + list(after) if p == pid},
                         key=lambda e: ENGINE_ORDER.index(e) if e in ENGINE_ORDER else 99)
        for eng in engines:
            b = before.get((pid, eng)) or {"answer": {}, "claims": []}
            a = after.get((pid, eng)) or {"answer": {}, "claims": []}
            sb, sa = snapshot(b["answer"], b["claims"], focus), snapshot(a["answer"], a["claims"], focus)
            rows.append({"fix_id": fix["fix_id"], "prompt_id": pid, "engine": eng, "epoch": fix["epoch"], "issue_id": fix["issue_id"],
                         "title": fix["title"], "tier": fix["tier"], "asset_type": fix["asset_type"], "reviewer": fix.get("reviewer"),
                         "approved_at": approved_at, "measured_at": now, "elapsed_s": elapsed_s,
                         "prompt_text": (prompt_texts or {}).get(pid), "status": "ok" if sa["ok"] else "engine_error",
                         **{f"before_{k}": sb[k] for k in _SIDES},
                         **{f"after_{k}": sa[k] for k in _SIDES},
                         "before_claim_tags": sb["tags"], "after_claim_tags": sa["tags"]})
    return rows


def _worst(tag_lists):
    tags = [t for ts in tag_lists for t in (ts or [])]
    return min(tags, key=TAG_SEVERITY.index) if tags else None


def summarize(rows, current_epoch):
    by_fix = {}
    for r in rows:
        by_fix.setdefault(r["fix_id"], []).append(r)
    out = []
    for fid, rs in by_fix.items():
        head = rs[0]
        prompts = []
        for pid in dict.fromkeys(r["prompt_id"] for r in rs):
            pr = [r for r in rs if r["prompt_id"] == pid]
            side = lambda k: {"mentioned": sum(bool(r[f"{k}_mentioned"]) for r in pr),
                              "owned_cited": sum(bool(r[f"{k}_owned_cited"]) for r in pr),
                              "tag": _worst(r[f"{k}_claim_tags"] for r in pr)}
            prompts.append({"prompt_id": pid, "prompt_text": pr[0].get("prompt_text"), "before": side("before"), "after": side("after"),
                            "answers": [{"engine": r["engine"], "status": r["status"], "before_answer": r["before_answer"],
                                         "after_answer": r["after_answer"], "before_cited": r["before_cited"],
                                         "after_cited": r["after_cited"]} for r in pr]})
        engines = {r["engine"] for r in rs}
        answered = {r["engine"] for r in rs if r["status"] == "ok"}
        out.append({"fix_id": fid, "title": head["title"], "tier": head["tier"], "asset_type": head["asset_type"],
                    "reviewer": head.get("reviewer"), "approved_at": head.get("approved_at"), "measured_at": head.get("measured_at"),
                    "epoch": head["epoch"], "rehearsal": head["epoch"] != current_epoch, "engines_answered": len(answered),
                    "engines_total": len(engines), "elapsed_s": head.get("elapsed_s"), "prompts": prompts})
    return sorted(out, key=lambda e: str(e.get("approved_at") or e.get("measured_at")), reverse=True)
