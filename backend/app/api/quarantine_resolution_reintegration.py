"""API for PHOENIX v21.151 quarantine resolution and reintegration governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.quarantine_resolution_reintegration import QuarantineResolutionReintegrationService

router = APIRouter(prefix="/v1/quarantine-resolution-reintegration", tags=["quarantine-resolution-reintegration"])
service = QuarantineResolutionReintegrationService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    resolution_readiness: dict
    quarantine_record: dict
    source_key: str
    max_stage: int = 3


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.151",
        "status": "active",
        "execution": False,
        "autonomous_quarantine_removal": False,
        "autonomous_routing_mutation": False,
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
        raise HTTPException(status_code=404, detail="reintegration record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    try:
        if payload.action == "approve":
            return service.approve(record_id, human_approved=payload.human_approved).__dict__
        if payload.action == "advance-stage":
            return service.advance_stage(record_id, human_approved=payload.human_approved).__dict__
        raise HTTPException(status_code=400, detail="unsupported action")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
