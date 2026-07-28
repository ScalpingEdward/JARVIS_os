"""API contract for PHOENIX v21.150 containment effectiveness observation."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.containment_effectiveness_observation import (
    ContainmentEffectivenessObservationService,
    ContainmentObservationSample,
)

router = APIRouter(prefix="/v1/containment-effectiveness", tags=["containment-effectiveness"])
service = ContainmentEffectivenessObservationService()


class SampleIn(BaseModel):
    sample_id: str
    capability: str
    available: bool
    fallback_healthy: bool
    dependency_satisfied: bool
    latency_ms: float
    confidence: float
    freshness: float


class ObserveIn(BaseModel):
    record_id: str
    workspace_id: str
    containment: dict
    samples: list[SampleIn] = Field(default_factory=list)
    source_key: str
    max_latency_ms: float = 1500.0


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.150",
        "status": "active",
        "execution": False,
        "autonomous_fallback_activation": False,
        "autonomous_quarantine_resolution": False,
    }


@router.post("/records")
def create_record(payload: ObserveIn) -> dict:
    try:
        samples = [ContainmentObservationSample(**item.model_dump()) for item in payload.samples]
        return service.observe(
            record_id=payload.record_id,
            workspace_id=payload.workspace_id,
            containment=payload.containment,
            samples=samples,
            source_key=payload.source_key,
            max_latency_ms=payload.max_latency_ms,
        ).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [record.__dict__ for record in service.list_records(workspace_id)]


@router.get("/records/{record_id}")
def record(record_id: str) -> dict:
    try:
        return service.get(record_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve-resolution-readiness":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve_resolution_readiness(record_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
