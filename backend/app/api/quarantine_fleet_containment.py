"""API contract for PHOENIX v21.149 quarantine fleet containment governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.quarantine_fleet_containment import Dependency, QuarantineFleetContainmentService

router = APIRouter(prefix="/v1/quarantine-fleet-containment", tags=["quarantine-fleet-containment"])
service = QuarantineFleetContainmentService()


class DependencyIn(BaseModel):
    consumer_id: str
    capability: str
    critical: bool = False
    fallback_consumer_id: str | None = None
    fallback_ready: bool = False


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    quarantine: dict
    dependencies: list[DependencyIn] = Field(default_factory=list)
    source_key: str


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.149",
        "status": "active",
        "execution": False,
        "autonomous_fallback_activation": False,
        "autonomous_route_mutation": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        deps = [Dependency(**item.model_dump()) for item in payload.dependencies]
        return service.create(
            record_id=payload.record_id,
            workspace_id=payload.workspace_id,
            quarantine=payload.quarantine,
            dependencies=deps,
            source_key=payload.source_key,
        ).__dict__
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
        raise HTTPException(status_code=404, detail="containment record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    try:
        if payload.action == "approve":
            return service.approve(record_id, human_approved=payload.human_approved).__dict__
        if payload.action == "approve-fallback-activation":
            return service.approve_fallback_activation(record_id, human_approved=payload.human_approved).__dict__
        raise HTTPException(status_code=400, detail="unsupported action")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
