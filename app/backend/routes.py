import mimetypes
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from backend import deps
from geologic.datagen.signals import SEEDED

router = APIRouter()

def _user(req: Request) -> str:
    return req.headers.get("X-Forwarded-Email", "presenter")

@router.get("/model/summary")
def model_summary(reads=Depends(deps.get_reads)):
    return reads.model_summary()

@router.get("/model/prompts/{prompt_id}")
def prompt_detail(prompt_id: str, reads=Depends(deps.get_reads)):
    d = reads.prompt_detail(prompt_id)
    if d is None:
        raise HTTPException(404, "Unknown question")
    return d

@router.get("/prompts")
def prompt_inventory(reads=Depends(deps.get_reads)):
    return reads.prompt_inventory()

@router.get("/opportunities/{opp_id}/evidence")
def opportunity_evidence(opp_id: str, reads=Depends(deps.get_reads), repo=Depends(deps.get_suggestions)):
    ev = reads.opportunity_evidence(opp_id)
    if ev is None:
        raise HTTPException(404, "Unknown opportunity")
    try:
        ev["live_page"] = repo.live_page(ev["page_id"]) if ev.get("page_id") else None
    except Exception as e:
        print(f"live_page {ev.get('page_id')}: {type(e).__name__}: {e}")
        ev["live_page"] = None
    return ev

@router.get("/prompts/search")
def prompt_search(q: str = "", reads=Depends(deps.get_reads)):
    if not q.strip():
        raise HTTPException(400, "Type a question to research.")
    pid = reads.prompt_search(q.strip())
    if pid is None:
        raise HTTPException(404, "No matching question found.")
    return {"prompt_id": pid}

@router.get("/prompts/{prompt_id}")
def prompt_explorer(prompt_id: str, reads=Depends(deps.get_reads)):
    d = reads.prompt_explorer(prompt_id)
    if d is None:
        raise HTTPException(404, "Unknown question")
    return d

@router.post("/prompts/{prompt_id}/track")
def track_prompt(prompt_id: str, req: Request, reads=Depends(deps.get_reads)):
    if not reads.track_prompt(prompt_id, _user(req)):
        raise HTTPException(404, "Unknown question")
    return {"tracked": True}

@router.get("/signals")
def signals(limit: int = 50, reads=Depends(deps.get_reads)):
    return reads.signals(min(max(limit, 1), 200))

@router.get("/signals/{signal_id}/image")
def signal_image(signal_id: str, reads=Depends(deps.get_reads)):
    path = reads.image_path(signal_id)
    if not path:
        raise HTTPException(404, "No image for this signal")
    # Apps have no /Volumes mount; stream the file through the Files API.
    body = deps._w().files.download(path).contents.read()
    return Response(body, media_type=mimetypes.guess_type(path)[0] or "image/png", headers={"Cache-Control": "max-age=3600"})

@router.get("/opportunities")
def opportunities(reads=Depends(deps.get_reads)):
    return reads.opportunities()

@router.get("/suggestions")
def suggestions(repo=Depends(deps.get_suggestions)):
    return repo.list()

@router.post("/suggestions/{sid}/approve", status_code=202)
def approve(sid: str, req: Request, repo=Depends(deps.get_suggestions), jobs=Depends(deps.get_jobs)):
    if not repo.claim(sid, _user(req)):
        raise HTTPException(409, "This suggestion is already publishing or no longer needs review.")
    try:
        run_id = jobs.run_publish(sid)
    except Exception as e:
        print(f"approve {sid}: could not start publish job: {type(e).__name__}: {e}")
        repo.release(sid, "Publish failed. Try again.")
        raise HTTPException(502, "Couldn't start publishing. Try again.")
    repo.set_run(sid, run_id)
    return {"run_id": run_id}

@router.post("/suggestions/{sid}/reject")
def reject(sid: str, req: Request, repo=Depends(deps.get_suggestions)):
    if not repo.reject(sid, _user(req)):
        raise HTTPException(409, "Only suggestions waiting for review can be rejected.")
    return {"state": "rejected"}

@router.get("/suggestions/{sid}/status")
def status(sid: str, repo=Depends(deps.get_suggestions), reads=Depends(deps.get_reads)):
    s = repo.status(sid)
    if s is None:
        raise HTTPException(404, "Unknown suggestion")
    if s["state"] == "published":
        ba = reads.before_after(s["prompt_ids"])
        s.update(ba or {})
        s["summary"] = reads.cluster_before_after(s["prompt_ids"])
        if ba:
            try:  # proof is a nice-to-have: never fail the poll over it
                row = repo.get(sid) or {}
                repo.save_proof(sid, row.get("title") or sid, row.get("reviewer"), ba, s["summary"])
            except Exception as e:
                print(f"save_proof {sid}: {type(e).__name__}: {e}")
    return s

@router.get("/impact")
def impact(reads=Depends(deps.get_reads), repo=Depends(deps.get_suggestions)):
    try:  # safety net: a publish that finished with the Fix page closed still gets its proof row
        u = repo.latest_published_without_proof()
        if u:
            ba = reads.before_after(u["prompt_ids"])
            if ba is not None:
                repo.save_proof(u["suggestion_id"], u.get("title") or u["suggestion_id"], u.get("reviewer"), ba,
                                reads.cluster_before_after(u["prompt_ids"]))
    except Exception as e:
        print(f"proof safety net: {type(e).__name__}: {e}")
    try:
        proof = repo.latest_proof()
    except Exception as e:  # proof_results missing on an old Lakebase: show the empty state
        print(f"latest_proof: {type(e).__name__}: {e}")
        proof = None
    return {"weekly": reads.weekly(), "health": repo.health(), "proof": proof}

class Ask(BaseModel):
    question: str

@router.post("/ask")
def ask(body: Ask, sup=Depends(deps.get_supervisor)):
    if not body.question.strip():
        raise HTTPException(400, "Type a question first.")
    return {"answer": sup.ask(body.question.strip())}

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
