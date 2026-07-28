"""API contract for PHOENIX v21.143 incident episode closure governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.incident_episode_closure import IncidentEpisodeClosureService

router = APIRouter(prefix="/v1/incident-episode-closure", tags=["incident-episode-closure"])
service = IncidentEpisodeClosureService()


class CreateIn(BaseModel):
    closure_id: str
    workspace_id: str
    incident_id: str
    stable_observation: dict
    baseline_before: float
    source_key: str
    max_adjustment: float = 0.05


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {"module": "v21.143", "status": "active", "execution": False, "autonomous_baseline_mutation": False}


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        return service.create(**payload.model_dump()).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id)]


@router.get("/records/{closure_id}")
def record(closure_id: str) -> dict:
    try:
        return service.get(closure_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="closure not found") from exc


@router.post("/records/{closure_id}/actions")
def action(closure_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(closure_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
