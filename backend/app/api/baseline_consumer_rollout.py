"""API contract for PHOENIX v21.146 baseline consumer rollout governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.baseline_consumer_rollout import BaselineConsumerRolloutService

router = APIRouter(prefix="/v1/baseline-consumer-rollout", tags=["baseline-consumer-rollout"])
service = BaselineConsumerRolloutService()


class CreateIn(BaseModel):
    rollout_id: str
    workspace_id: str
    approved_preview: dict
    requested_consumers: list[str] = Field(default_factory=list)
    source_key: str
    max_stage: int = 3


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.146",
        "status": "active",
        "execution": False,
        "autonomous_policy_mutation": False,
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


@router.get("/records/{rollout_id}")
def record(rollout_id: str) -> dict:
    try:
        return service.get(rollout_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rollout not found") from exc


@router.post("/records/{rollout_id}/actions")
def action(rollout_id: str, payload: ActionIn) -> dict:
    try:
        if payload.action == "approve":
            return service.approve(rollout_id, human_approved=payload.human_approved).__dict__
        if payload.action == "advance-stage":
            return service.advance_stage(rollout_id, human_approved=payload.human_approved).__dict__
        raise HTTPException(status_code=400, detail="unsupported action")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
