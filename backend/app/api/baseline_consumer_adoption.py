"""API contract for PHOENIX v21.147 baseline consumer adoption governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.baseline_consumer_adoption import BaselineConsumerAdoptionService

router = APIRouter(prefix="/v1/baseline-consumer-adoption", tags=["baseline-consumer-adoption"])
service = BaselineConsumerAdoptionService()


class AdoptionIn(BaseModel):
    receipt_id: str
    workspace_id: str
    rollout: dict
    consumer_id: str
    consumer_type: str
    observed_baseline_id: str
    observed_baseline_version: int
    observed_baseline_digest: str
    source_key: str


class ActionIn(BaseModel):
    action: str
    human_reviewed: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.147",
        "status": "active",
        "autonomous_correction": False,
        "routing_mutation": False,
        "policy_mutation": False,
        "execution": False,
    }


@router.post("/records")
def create_record(payload: AdoptionIn) -> dict:
    try:
        return service.acknowledge(**payload.model_dump()).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id)]


@router.get("/records/{receipt_id}")
def record(receipt_id: str) -> dict:
    try:
        return service.get(receipt_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="receipt not found") from exc


@router.post("/records/{receipt_id}/actions")
def action(receipt_id: str, payload: ActionIn) -> dict:
    if payload.action != "review-drift":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.review_drift(receipt_id, human_reviewed=payload.human_reviewed).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
