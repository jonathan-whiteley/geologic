import mimetypes
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from backend import deps
from backend.search import SearchUnavailable
from geologic.config import settings
from geologic.datagen.reference import SUBJECTS, exclusion_rules
from geologic.datagen.signals import SEEDED
from geologic.publish_flow import FRIENDLY_ERROR, STEP_LABELS
from geologic.results import summarize

router = APIRouter()
_REASONS = {r["rule_id"]: r["reason"] for r in exclusion_rules()}


def _user(req: Request) -> str:
    return req.headers.get("X-Forwarded-Email", "presenter")


# Measure
@router.get("/model/summary")
def model_summary(reads=Depends(deps.get_reads)):
    return reads.model_summary()


@router.get("/prompts")
def prompts(reads=Depends(deps.get_reads)):
    return reads.prompt_rows()


@router.get("/prompt-suggestions")
def prompt_suggestions(reads=Depends(deps.get_reads)):
    return reads.prompt_suggestions()


# Fix: the queue, approve (fast path), Approve all T0 (job), reject, edit, status
@router.get("/fixes")
def fixes(repo=Depends(deps.get_fix_repo)):
    return repo.list()


@router.get("/fix/summary")
def fix_summary(repo=Depends(deps.get_fix_repo)):
    t = repo.tier_counts()
    return {"tiers": {"T0": {"ready": t.get("T0", 0)}, "T1": {"to_review": t.get("T1", 0)}, "T2": {"to_review": t.get("T2", 0)}},
            "quarantined": repo.quarantine_points()["count"], "review_mode": True}


def _fix_lite(f):
    return {k: f.get(k) for k in ("fix_id", "tier", "asset_type", "state")}


def _fixes_by_issue(repo):
    try:
        rows = repo.list()
    except Exception as e:   # Lakebase down: the issue queue still renders, without fix chips
        print(f"fixes for issues: {type(e).__name__}: {e}")
        rows = []
    out = {}
    for f in rows:
        out.setdefault(f["issue_id"], []).append(f)
    return out


@router.get("/issues")
def issues(type: str | None = None, cluster: str | None = None, reads=Depends(deps.get_reads), repo=Depends(deps.get_fix_repo)):
    by = _fixes_by_issue(repo)
    return [{**i, "fixes": [_fix_lite(f) for f in by.get(i["issue_id"], [])]} for i in reads.issues(type or None, cluster or None)]


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: str, reads=Depends(deps.get_reads), repo=Depends(deps.get_fix_repo)):
    d = reads.issue_detail(issue_id)
    if d is None:
        raise HTTPException(404, "Unknown issue")
    mine = _fixes_by_issue(repo).get(issue_id, [])
    mine.sort(key=lambda f: (f.get("tier") == "T2", f.get("tier") or "", f.get("asset_type") or ""))   # T2 last
    d["issue"]["fixes"] = [_fix_lite(f) for f in mine]
    d["fixes"] = mine
    return d


@router.post("/fixes/approve-t0", status_code=202)
def approve_t0(req: Request, repo=Depends(deps.get_fix_repo), jobs=Depends(deps.get_jobs)):
    ids = repo.claim_t0(_user(req))
    if not ids:
        raise HTTPException(409, "No T0 fixes are waiting.")
    try:
        run_id = jobs.run_publish(ids)
    except Exception as e:
        print(f"approve-t0: could not start publish job: {type(e).__name__}: {e}")
        repo.release_many(ids, FRIENDLY_ERROR)
        raise HTTPException(502, "Couldn't start publishing. Try again.")
    repo.set_run(ids, run_id)
    return {"run_id": run_id, "fix_ids": ids}


@router.post("/fixes/{fix_id}/approve", status_code=202)
def approve(fix_id: str, req: Request, repo=Depends(deps.get_fix_repo), publisher=Depends(deps.get_publisher)):
    if not repo.claim(fix_id, _user(req)):
        raise HTTPException(409, "This fix is already publishing or no longer needs review.")
    publisher.start(fix_id)
    return {"started": True}


@router.post("/fixes/{fix_id}/reject")
def reject(fix_id: str, req: Request, repo=Depends(deps.get_fix_repo)):
    if not repo.reject(fix_id, _user(req)):
        raise HTTPException(409, "Only fixes waiting for review can be rejected.")
    return {"state": "rejected"}


class EditBody(BaseModel):
    patch_text: str


@router.post("/fixes/{fix_id}/edit")
def edit(fix_id: str, body: EditBody, repo=Depends(deps.get_fix_repo), reads=Depends(deps.get_reads), chat=Depends(deps.get_chat)):
    from backend.fixes_edit import edit_fix
    from geologic.drafting import unsupported_claims
    fix = repo.get(fix_id)
    if fix is None:
        raise HTTPException(404, "Unknown fix")
    if fix["state"] != "pending_review":
        raise HTTPException(409, "Only fixes waiting for review can be edited.")
    text = (body.patch_text or "").strip()
    if not text:
        raise HTTPException(400, "The fix text is empty.")
    items, people = reads.item_names(), reads.personas()
    names = tuple(items) + tuple(p["display_name"] for p in people)
    judge = lambda t, g: unsupported_claims(t, g, chat, settings.judge_endpoint, SUBJECTS, names=names)
    final = edit_fix(fix, text, facts=reads.facts(), rules=reads.rules(), today=date.today(), item_names=items,
                     persona_names=people, judge=judge)
    updated = repo.edit(fix_id, text, final)
    if updated is None:
        raise HTTPException(409, "Only fixes waiting for review can be edited.")
    return updated


@router.get("/fixes/{fix_id}/status")
def fix_status(fix_id: str, repo=Depends(deps.get_fix_repo), clock=Depends(deps.get_clock)):
    s = repo.status(fix_id)
    if s is None:
        raise HTTPException(404, "Unknown fix")
    rv = s.get("reviewed_at")
    elapsed = int((clock() - rv).total_seconds()) if rv else None
    entry = fallback = None
    if s["state"] == "published" or (s["state"] == "publishing" and elapsed is not None and elapsed > settings.reask_fallback_s):
        epoch, rows = repo.epoch(), repo.results(fix_id)
        if s["state"] == "published":
            fresh = [r for r in rows if rv is None or r["measured_at"] >= rv]
            entry = (summarize(fresh, epoch) or [None])[0]
        else:   # still re-asking past the fallback window: a rehearsal (results measured before this approval) may stand in
            prev = [r for r in rows if r["measured_at"] < rv]
            if prev:
                fallback = {"rehearsed_at": max(r["measured_at"] for r in prev).isoformat(), "entry": summarize(prev, epoch)[0]}
    return {"state": s["state"], "publish_step": s["publish_step"], "step_labels": list(STEP_LABELS), "error": s.get("error"),
            "elapsed_s": elapsed, "entry": entry, "fallback": fallback}


@router.get("/quarantine")
def quarantine(repo=Depends(deps.get_fix_repo)):
    q = repo.quarantine_points()
    return {"count": q["count"], "rule_id": q["rule_id"], "reason": _REASONS.get(q["rule_id"]),
            "points": [{"enforcement_point": p["enforcement_point"], "occurred_at": p["occurred_at"]} for p in q["points"]]}


# Impact
@router.get("/impact")
def impact(reads=Depends(deps.get_reads), repo=Depends(deps.get_fix_repo)):
    return reads.impact(repo)


@router.get("/impact/citations")
def impact_citations(doc_id: str = "", reads=Depends(deps.get_reads)):
    rows = reads.doc_citations(doc_id)
    if rows is None:
        raise HTTPException(400, "Unknown document.")
    return rows


# Ask anything, Track and run
@router.get("/search")
def search(q: str = "", s=Depends(deps.get_search)):
    try:
        return s.search(q)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except SearchUnavailable:
        raise HTTPException(503, "Search is unavailable right now.")


class TrackBody(BaseModel):
    text: str
    suggestion_id: str | None = None


@router.post("/prompts/track")
def track(body: TrackBody, req: Request, tracker=Depends(deps.get_tracker)):
    try:
        return tracker.track(body.text, body.suggestion_id, _user(req))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except SearchUnavailable:
        raise HTTPException(503, "Search is unavailable right now.")


@router.get("/prompts/{prompt_id}")
def prompt_detail(prompt_id: str, reads=Depends(deps.get_reads)):
    d = reads.prompt_detail(prompt_id)
    if d is None:
        raise HTTPException(404, "Unknown prompt")
    return d


@router.get("/signals/{signal_id}/image")
def signal_image(signal_id: str, reads=Depends(deps.get_reads)):
    path = reads.image_path(signal_id)
    if not path:
        raise HTTPException(404, "No image for this signal")
    # Apps have no /Volumes mount; stream the file through the Files API.
    body = deps._w().files.download(path).contents.read()
    return Response(body, media_type=mimetypes.guess_type(path)[0] or "image/png", headers={"Cache-Control": "max-age=3600"})


@router.post("/demo/reset", status_code=202)
def demo_reset(jobs=Depends(deps.get_jobs)):
    return {"run_id": jobs.run_reset()}


@router.get("/demo/reset/{run_id}")
def demo_reset_status(run_id: int, jobs=Depends(deps.get_jobs)):
    st = jobs.reset_state(run_id)
    if st is None:
        raise HTTPException(404, "Unknown reset run")
    return st


@router.post("/demo/inject/{truth_id}", status_code=202)
def demo_inject(truth_id: str, jobs=Depends(deps.get_jobs)):
    if truth_id not in SEEDED:
        raise HTTPException(404, "Unknown seeded signal")
    return {"run_id": jobs.run_inject(truth_id)}


class GenieAsk(BaseModel):
    question: str
    conversation_id: str | None = None
    context: str | None = None


@router.post("/genie/ask")
def genie_ask(body: GenieAsk, genie=Depends(deps.get_genie)):
    if not body.question.strip():
        raise HTTPException(400, "Type a question first.")
    ctx = body.context.strip()[:300] if body.context and body.context.strip() else None
    return genie.ask(body.question.strip(), conversation_id=body.conversation_id or None, context=ctx)


@router.get("/genie/message/{conversation_id}/{message_id}")
def genie_message(conversation_id: str, message_id: str, genie=Depends(deps.get_genie)):
    return genie.get_message(conversation_id, message_id)
