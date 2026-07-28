from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, engine, evals


ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="AI Workflow Reliability Demo",
    description=(
        "A portfolio prototype showing how structured validation, source-system "
        "checks, idempotency, and human handoffs can make AI-assisted actions safer."
    ),
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class IntegrationUpdate(BaseModel):
    online: bool


class RunRequest(BaseModel):
    scenario_id: str | None = None
    transcript: str | None = None


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/bootstrap")
def bootstrap():
    db.init_db()
    return {
        "operation": db.agency(),
        "scenarios": engine.scenario_list(),
        "steps": engine.STEPS,
        "integrations": db.list_integrations(),
        "handoffs": db.recent_handoffs(),
        "runs": db.recent_runs(),
    }


@app.post("/api/reset")
def reset():
    db.init_db(reset=True)
    return bootstrap()


@app.post("/api/integrations/{key}")
def update_integration(key: str, update: IntegrationUpdate):
    known = {item[0] for item in db.INTEGRATIONS}
    if key not in known:
        raise HTTPException(status_code=404, detail="unknown integration")
    item = db.set_integration(key, update.online)
    return {"integration": item, "integrations": db.list_integrations()}


@app.post("/api/run")
def run(req: RunRequest):
    try:
        return engine.run_request(scenario_id=req.scenario_id, transcript=req.transcript)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/handoffs")
def handoffs():
    return {"handoffs": db.recent_handoffs()}


@app.post("/api/evals")
def run_evals():
    return evals.run_all()
