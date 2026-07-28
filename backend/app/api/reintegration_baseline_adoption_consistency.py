"""API contract for PHOENIX v21.156."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.reintegration_baseline_adoption_consistency import (
    AdoptionReceipt,
    ReintegrationBaselineAdoptionConsistencyService,
)

router = APIRouter(prefix="/v1/reintegration-baseline-adoption", tags=["reintegration-baseline-adoption"])
service = ReintegrationBaselineAdoptionConsistencyService()


class ReceiptIn(BaseModel):
    receipt_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    consumer_state: str
    source_digest: str


class CreateIn(BaseModel):
    record_id: str
    workspace_id: str
    active_rollout: dict
    receipts: list[ReceiptIn] = Field(default_factory=list)
    source_key: str


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.156",
        "status": "active",
        "execution": False,
        "autonomous_consumer_mutation": False,
    }


@router.post("/records")
def create_record(payload: CreateIn) -> dict:
    try:
        receipts = [AdoptionReceipt(**r.model_dump()) for r in payload.receipts]
        return service.create(
            record_id=payload.record_id,
            workspace_id=payload.workspace_id,
            active_rollout=payload.active_rollout,
            receipts=receipts,
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
