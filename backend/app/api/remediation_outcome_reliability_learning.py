"""API contract for PHOENIX v21.161 remediation reliability learning governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.remediation_outcome_reliability_learning import RemediationOutcomeReliabilityLearningService

router = APIRouter(prefix="/v1/remediation-reliability-learning", tags=["remediation-reliability-learning"])
service = RemediationOutcomeReliabilityLearningService()


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    remediation_episode_id: str
    closed_episode: dict
    baseline_before: float
    source_key: str
    max_adjustment: float = 0.05
    min_confidence: float = 0.80
    max_residual_risk: float = 0.20


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.161",
        "status": "active",
        "execution": False,
        "autonomous_baseline_mutation": False,
        "autonomous_runtime_mutation": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        return service.create(**payload.model_dump()).__dict__
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [record.__dict__ for record in service.list_records(workspace_id)]


@router.get("/records/{record_id}")
def record(record_id: str) -> dict:
    try:
        return service.get(record_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="learning record not found") from exc


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
