from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
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
    return FileResponse(path, media_type="image/png")

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
    run_id = jobs.run_publish(sid)
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
        s.update(reads.before_after(s["prompt_ids"]) or {})
        s["summary"] = reads.cluster_before_after(s["prompt_ids"])
    return s

@router.get("/impact")
def impact(reads=Depends(deps.get_reads), repo=Depends(deps.get_suggestions)):
    return {"weekly": reads.weekly(), "health": repo.health()}

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

@router.post("/demo/inject/{truth_id}", status_code=202)
def demo_inject(truth_id: str, jobs=Depends(deps.get_jobs)):
    if truth_id not in SEEDED:
        raise HTTPException(404, "Unknown seeded signal")
    return {"run_id": jobs.run_inject(truth_id)}
