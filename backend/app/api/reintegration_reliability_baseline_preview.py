"""API contract for PHOENIX v21.154 reintegration reliability baseline preview governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.reintegration_reliability_baseline_preview import ReintegrationReliabilityBaselinePreviewService

router = APIRouter(prefix="/v1/reintegration-reliability-preview", tags=["reintegration-reliability-preview"])
service = ReintegrationReliabilityBaselinePreviewService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    closed_episode: dict
    current_reliability: float
    source_key: str
    max_score_delta: float = 0.10
    max_blast_radius: float = 0.30
    max_residual_risk: float = 0.25


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.154",
        "status": "active",
        "simulation_only": True,
        "autonomous_baseline_mutation": False,
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
        raise HTTPException(status_code=404, detail="preview not found") from exc


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
