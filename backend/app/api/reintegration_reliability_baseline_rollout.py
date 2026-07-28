"""API for PHOENIX v21.155 reintegration reliability baseline rollout governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.reintegration_reliability_baseline_rollout import ReintegrationReliabilityBaselineRolloutService

router = APIRouter(prefix="/v1/reintegration-reliability-rollout", tags=["reintegration-reliability-rollout"])
service = ReintegrationReliabilityBaselineRolloutService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    approved_preview: dict
    consumers: list[str] = Field(default_factory=list)
    source_key: str
    max_stage: int = 3


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.155",
        "status": "active",
        "autonomous_baseline_mutation": False,
        "autonomous_consumer_activation": False,
        "execution": False,
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
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions")
def action(record_id: str, payload: ActionIn) -> dict:
    try:
        if payload.action == "approve-commit":
            return service.approve_commit(record_id, human_approved=payload.human_approved).__dict__
        if payload.action == "advance-stage":
            return service.advance_stage(record_id, human_approved=payload.human_approved).__dict__
        raise HTTPException(status_code=400, detail="unsupported action")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
