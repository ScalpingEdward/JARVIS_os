"""API contract for PHOENIX v21.141 primary recovery reconciliation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.primary_recovery_reconciliation import PrimaryRecoveryReconciliationService, RecoveryReceipt

router = APIRouter(prefix="/v1/recovery-primary-reconciliation", tags=["recovery-primary-reconciliation"])
service = PrimaryRecoveryReconciliationService()


class ReceiptIn(BaseModel):
    receipt_id: str
    permit_id: str
    recovery_plan_digest: str
    primary_adapter_id: str
    primary_worker_id: str
    gateway_id: str
    operation: str
    target: str
    response_digest: str
    success: bool
    side_effects: list[str] = Field(default_factory=list)


class ReconcileIn(BaseModel):
    attestation_id: str
    workspace_id: str
    source_key: str
    consumed_permit: dict
    receipt: ReceiptIn


class ActionIn(BaseModel):
    action: str
    human_approved: bool = False


@router.get("/status")
def status() -> dict:
    return {"module": "v21.141", "status": "active", "execution": False}


@router.post("/records")
def create_record(payload: ReconcileIn) -> dict:
    try:
        receipt = RecoveryReceipt(**payload.receipt.model_dump())
        return service.reconcile(
            attestation_id=payload.attestation_id,
            workspace_id=payload.workspace_id,
            consumed_permit=payload.consumed_permit,
            receipt=receipt,
            source_key=payload.source_key,
        ).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id)]


@router.get("/records/{attestation_id}")
def record(attestation_id: str) -> dict:
    try:
        return service.get(attestation_id).__dict__
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="attestation not found") from exc


@router.post("/records/{attestation_id}/actions")
def action(attestation_id: str, payload: ActionIn) -> dict:
    if payload.action != "approve":
        raise HTTPException(status_code=400, detail="unsupported action")
    try:
        return service.approve(attestation_id, human_approved=payload.human_approved).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
