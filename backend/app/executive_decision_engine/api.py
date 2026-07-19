from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..executive_strategy.api import router as executive_strategy_router
from ..executive_trading_incident_recovery.api import router as executive_trading_incident_recovery_router
from ..executive_trading_readiness.api import router as executive_trading_readiness_router
from .models import (
    ApprovalRequest,
    AuditRecord,
    DecisionListResponse,
    DecisionStatusResponse,
    ExecutiveDecision,
    ExecutiveDecisionCreate,
)
from .service import executive_decision_service
from .trading_api import router as trading_decision_router

router = APIRouter(tags=["executive-decisions"])


@router.get("/v1/executive-decisions/status", response_model=DecisionStatusResponse)
def decision_status(workspace_id: str = Query(min_length=1, max_length=100)) -> DecisionStatusResponse:
    return executive_decision_service.status(workspace_id)


@router.post("/v1/executive-decisions", response_model=ExecutiveDecision, status_code=status.HTTP_201_CREATED)
def create_decision(payload: ExecutiveDecisionCreate) -> ExecutiveDecision:
    try:
        return executive_decision_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-decisions", response_model=DecisionListResponse)
def list_decisions(workspace_id: str = Query(min_length=1, max_length=100)) -> DecisionListResponse:
    items = executive_decision_service.list_decisions(workspace_id)
    return DecisionListResponse(items=items, count=len(items))


@router.get("/v1/executive-decisions/{decision_id}", response_model=ExecutiveDecision)
def get_decision(decision_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    record = executive_decision_service.get(decision_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive decision not found")
    return record


@router.post("/v1/executive-decisions/{decision_id}/evaluate", response_model=ExecutiveDecision)
def evaluate_decision(decision_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    try:
        return executive_decision_service.evaluate(decision_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-decisions/{decision_id}/approve", response_model=ExecutiveDecision)
def approve_decision(decision_id: UUID, request: ApprovalRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    try:
        return executive_decision_service.approve(decision_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-decisions/audit", response_model=list[AuditRecord])
def decision_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_decision_service.audit_records(workspace_id)


router.include_router(trading_decision_router)
router.include_router(executive_trading_readiness_router)
router.include_router(executive_trading_incident_recovery_router)
router.include_router(executive_strategy_router)
