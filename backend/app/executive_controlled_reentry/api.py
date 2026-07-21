from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CanaryResultRequest,
    ControlledReentryAssessment,
    ControlledReentryAssessmentCreate,
    ControlledReentryStatusResponse,
    FullReenableRequest,
)
from .service import executive_controlled_reentry_service

router = APIRouter(tags=["executive-controlled-reentry"])


@router.get("/v1/executive-controlled-reentry/status", response_model=ControlledReentryStatusResponse)
def reentry_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ControlledReentryStatusResponse:
    return executive_controlled_reentry_service.status(workspace_id)


@router.post("/v1/executive-controlled-reentry/assessments", response_model=ControlledReentryAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ControlledReentryAssessmentCreate) -> ControlledReentryAssessment:
    try:
        return executive_controlled_reentry_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-controlled-reentry/assessments", response_model=list[ControlledReentryAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ControlledReentryAssessment]:
    return executive_controlled_reentry_service.list_assessments(workspace_id)


@router.get("/v1/executive-controlled-reentry/assessments/{record_id}", response_model=ControlledReentryAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ControlledReentryAssessment:
    record = executive_controlled_reentry_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Controlled re-entry record not found")
    return record


@router.post("/v1/executive-controlled-reentry/canary", response_model=ControlledReentryAssessment)
def record_canary(request: CanaryResultRequest) -> ControlledReentryAssessment:
    try:
        return executive_controlled_reentry_service.record_canary(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-controlled-reentry/full-reenable", response_model=ControlledReentryAssessment)
def full_reenable(request: FullReenableRequest) -> ControlledReentryAssessment:
    try:
        return executive_controlled_reentry_service.full_reenable(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-controlled-reentry/audit", response_model=list[AuditRecord])
def reentry_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_controlled_reentry_service.audit_records(workspace_id)
