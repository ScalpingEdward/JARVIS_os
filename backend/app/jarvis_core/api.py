from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CoreDecision,
    CoreDecisionCreate,
    CoreDecisionListResponse,
    CoreStatus,
    DecisionApprovalRequest,
)
from .service import jarvis_core_service

router = APIRouter(prefix="/v1/jarvis-core", tags=["jarvis-core"])


@router.get("/status", response_model=CoreStatus)
def core_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CoreStatus:
    return jarvis_core_service.status(workspace_id)


@router.post("/decisions", response_model=CoreDecision, status_code=status.HTTP_201_CREATED)
def create_decision(payload: CoreDecisionCreate) -> CoreDecision:
    return jarvis_core_service.create(payload)


@router.get("/decisions", response_model=CoreDecisionListResponse)
def list_decisions(workspace_id: str = Query(min_length=1, max_length=100)) -> CoreDecisionListResponse:
    items = jarvis_core_service.list_decisions(workspace_id)
    return CoreDecisionListResponse(items=items, count=len(items))


@router.get("/decisions/{decision_id}", response_model=CoreDecision)
def get_decision(decision_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> CoreDecision:
    decision = jarvis_core_service.get(decision_id, workspace_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="JARVIS core decision not found")
    return decision


@router.post("/decisions/{decision_id}/analyze", response_model=CoreDecision)
def analyze_decision(
    decision_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> CoreDecision:
    decision = jarvis_core_service.analyze(decision_id, workspace_id, actor_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="JARVIS core decision not found")
    return decision


@router.post("/decisions/{decision_id}/approval", response_model=CoreDecision)
def approve_decision(decision_id: UUID, payload: DecisionApprovalRequest) -> CoreDecision:
    try:
        decision = jarvis_core_service.approve(decision_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(status_code=404, detail="JARVIS core decision not found")
    return decision


@router.get("/audit", response_model=list[AuditRecord])
def audit_records(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return jarvis_core_service.audit(workspace_id)
