"""API contract for PHOENIX v21.160 coordinated recovery stability governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.coordinated_recovery_stability import (
    ConsumerObservation,
    CoordinatedRecoveryStabilityService,
)

router = APIRouter(prefix="/v1/coordinated-recovery-stability", tags=["coordinated-recovery-stability"])
service = CoordinatedRecoveryStabilityService()


class ObservationIn(BaseModel):
    consumer_id: str
    health: float = Field(ge=0.0, le=1.0)
    baseline_match: bool
    dependency_satisfaction: float = Field(ge=0.0, le=1.0)
    latency_quality: float = Field(ge=0.0, le=1.0)
    error_quality: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    completion_evidence: dict
    observations: list[ObservationIn]
    source_key: str
    min_stability_score: float = 0.80
    min_confidence: float = 0.80
    max_residual_risk: float = 0.20


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.160",
        "status": "active",
        "execution": False,
        "autonomous_consumer_mutation": False,
        "autonomous_baseline_mutation": False,
        "autonomous_route_mutation": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        observations = [ConsumerObservation(**item.model_dump()) for item in payload.observations]
        return service.create(
            record_id=payload.record_id,
            workspace_id=payload.workspace_id,
            completion_evidence=payload.completion_evidence,
            observations=observations,
            source_key=payload.source_key,
            min_stability_score=payload.min_stability_score,
            min_confidence=payload.min_confidence,
            max_residual_risk=payload.max_residual_risk,
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
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve-close":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(record_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
