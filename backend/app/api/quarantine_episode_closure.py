"""API contract for PHOENIX v21.153 quarantine episode closure governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.quarantine_episode_closure import QuarantineEpisodeClosureService

router = APIRouter(prefix="/v1/quarantine-episode-closure", tags=["quarantine-episode-closure"])
service = QuarantineEpisodeClosureService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    quarantine_id: str
    stable_evidence: dict
    current_reliability: float
    source_key: str
    max_adjustment: float = 0.05


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.153",
        "status": "active",
        "execution": False,
        "autonomous_runtime_mutation": False,
        "autonomous_reliability_mutation": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        return service.create(**payload.model_dump()).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id)]


@router.get("/records/{record_id}")
def record(record_id: str) -> dict:
    try:
        return service.get(record_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="closure record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(record_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
