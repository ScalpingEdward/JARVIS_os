from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ContinuityAssessment,
    ContinuityAssessmentCreate,
    ContinuityStatusResponse,
    FailoverRequest,
    RecoveryRequest,
)
from .service import executive_operational_continuity_service

router = APIRouter(tags=["executive-operational-continuity"])


@router.get("/v1/executive-operational-continuity/status", response_model=ContinuityStatusResponse)
def continuity_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ContinuityStatusResponse:
    return executive_operational_continuity_service.status(workspace_id)


@router.post("/v1/executive-operational-continuity/assessments", response_model=ContinuityAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ContinuityAssessmentCreate) -> ContinuityAssessment:
    try:
        return executive_operational_continuity_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-operational-continuity/assessments", response_model=list[ContinuityAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ContinuityAssessment]:
    return executive_operational_continuity_service.list_assessments(workspace_id)


@router.get("/v1/executive-operational-continuity/assessments/{record_id}", response_model=ContinuityAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ContinuityAssessment:
    record = executive_operational_continuity_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Operational continuity record not found")
    return record


@router.post("/v1/executive-operational-continuity/failover", response_model=ContinuityAssessment)
def failover(request: FailoverRequest) -> ContinuityAssessment:
    try:
        return executive_operational_continuity_service.failover(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-operational-continuity/recover", response_model=ContinuityAssessment)
def recover(request: RecoveryRequest) -> ContinuityAssessment:
    try:
        return executive_operational_continuity_service.recover(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-operational-continuity/audit", response_model=list[AuditRecord])
def continuity_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_operational_continuity_service.audit_records(workspace_id)
