from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import (
    ApprovalConsume,
    ApprovalDecision,
    ApprovalListResponse,
    ApprovalRecord,
    ApprovalRequestCreate,
    ApprovalStatus,
    ApprovalTokenResponse,
    AuditListResponse,
)
from .service import ApprovalError, approval_service

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


@router.post("", response_model=ApprovalRecord, status_code=201)
def request_approval(payload: ApprovalRequestCreate) -> ApprovalRecord:
    try:
        return approval_service.request(payload)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=ApprovalListResponse)
def list_approvals(approval_status: ApprovalStatus | None = None) -> ApprovalListResponse:
    items = approval_service.list(status=approval_status)
    return ApprovalListResponse(items=items, count=len(items))


@router.post("/{approval_id}/approve", response_model=ApprovalTokenResponse)
def approve(approval_id: UUID, payload: ApprovalDecision) -> ApprovalTokenResponse:
    try:
        return approval_service.approve(approval_id, payload)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{approval_id}/reject", response_model=ApprovalRecord)
def reject(approval_id: UUID, payload: ApprovalDecision) -> ApprovalRecord:
    try:
        return approval_service.reject(approval_id, payload)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{approval_id}/consume", response_model=ApprovalRecord)
def consume(approval_id: UUID, payload: ApprovalConsume) -> ApprovalRecord:
    try:
        return approval_service.consume(approval_id, payload.confirmation_token, payload.actor)
    except ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit/events", response_model=AuditListResponse)
def audit_events() -> AuditListResponse:
    items = approval_service.audit_events()
    return AuditListResponse(items=items, count=len(items))
