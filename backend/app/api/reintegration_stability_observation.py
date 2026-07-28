"""API for PHOENIX v21.152 reintegration stability observation."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.reintegration_stability_observation import (
    ReintegrationStabilityObservationService,
    StabilitySample,
)

router = APIRouter(prefix="/v1/reintegration-stability", tags=["reintegration-stability"])
service = ReintegrationStabilityObservationService()


class SampleIn(BaseModel):
    consumer_healthy: bool
    baseline_match: bool
    dependency_satisfied: bool
    latency_ms: float
    confidence: float
    freshness: float
    error_rate: float = 0.0


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    reintegration: dict
    samples: list[SampleIn] = Field(min_length=1)
    source_key: str
    max_latency_ms: float = 1000.0
    max_error_rate: float = 0.05
    min_confidence: float = 0.80
    max_residual_risk: float = 0.25


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.152",
        "status": "active",
        "autonomous_quarantine_closure": False,
        "routing_mutation_enabled": False,
        "execution_enabled": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        samples = [StabilitySample(**sample.model_dump()) for sample in payload.samples]
        return service.observe(
            record_id=payload.record_id,
            workspace_id=payload.workspace_id,
            reintegration=payload.reintegration,
            samples=samples,
            source_key=payload.source_key,
            max_latency_ms=payload.max_latency_ms,
            max_error_rate=payload.max_error_rate,
            min_confidence=payload.min_confidence,
            max_residual_risk=payload.max_residual_risk,
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
    if payload.action != "approve":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(record_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
