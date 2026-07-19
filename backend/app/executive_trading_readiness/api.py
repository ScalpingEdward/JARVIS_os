from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ReadinessAssessment, ReadinessInput, ReadinessListResponse, ReadinessStatusResponse
from .service import executive_trading_readiness_service

router = APIRouter(tags=["executive-trading-readiness"])


@router.get("/v1/executive-trading-readiness/status", response_model=ReadinessStatusResponse)
def readiness_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ReadinessStatusResponse:
    return executive_trading_readiness_service.status(workspace_id)


@router.post("/v1/executive-trading-readiness/assessments", response_model=ReadinessAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ReadinessInput) -> ReadinessAssessment:
    try:
        return executive_trading_readiness_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trading-readiness/assessments", response_model=ReadinessListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> ReadinessListResponse:
    items = executive_trading_readiness_service.list_assessments(workspace_id)
    return ReadinessListResponse(items=items, count=len(items))


@router.get("/v1/executive-trading-readiness/assessments/{assessment_id}", response_model=ReadinessAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ReadinessAssessment:
    item = executive_trading_readiness_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trading readiness assessment not found")
    return item


@router.get("/v1/executive-trading-readiness/audit", response_model=list[AuditRecord])
def readiness_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_trading_readiness_service.audit_records(workspace_id)
