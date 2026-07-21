from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CopyExecutionAssessment,
    CopyExecutionAssessmentCreate,
    CopyExecutionStatusResponse,
    DriftRepairRequest,
)
from .service import executive_copy_execution_drift_repair_service

router = APIRouter(tags=["executive-copy-execution-drift-repair"])


@router.get("/v1/executive-copy-execution-drift-repair/status", response_model=CopyExecutionStatusResponse)
def copy_execution_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CopyExecutionStatusResponse:
    return executive_copy_execution_drift_repair_service.status(workspace_id)


@router.post(
    "/v1/executive-copy-execution-drift-repair/assessments",
    response_model=CopyExecutionAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: CopyExecutionAssessmentCreate) -> CopyExecutionAssessment:
    try:
        return executive_copy_execution_drift_repair_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-copy-execution-drift-repair/assessments", response_model=list[CopyExecutionAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[CopyExecutionAssessment]:
    return executive_copy_execution_drift_repair_service.list_assessments(workspace_id)


@router.get("/v1/executive-copy-execution-drift-repair/assessments/{record_id}", response_model=CopyExecutionAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> CopyExecutionAssessment:
    record = executive_copy_execution_drift_repair_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Copy execution fanout record not found")
    return record


@router.post("/v1/executive-copy-execution-drift-repair/repair", response_model=CopyExecutionAssessment)
def repair_drift(request: DriftRepairRequest) -> CopyExecutionAssessment:
    try:
        return executive_copy_execution_drift_repair_service.repair(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-copy-execution-drift-repair/audit", response_model=list[AuditRecord])
def copy_execution_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_copy_execution_drift_repair_service.audit_records(workspace_id)
