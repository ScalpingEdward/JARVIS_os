from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PipelineAssessment, PipelineAssessmentCreate, PipelineExecuteRequest, PipelineStatus
from .service import end_to_end_runtime_validation_service

router = APIRouter(tags=["executive-mt5-end-to-end-runtime-validation"])


@router.get("/v1/executive-mt5-runtime-validation/status", response_model=PipelineStatus)
def pipeline_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PipelineStatus:
    return end_to_end_runtime_validation_service.status(workspace_id)


@router.post("/v1/executive-mt5-runtime-validation/assessments", response_model=PipelineAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: PipelineAssessmentCreate) -> PipelineAssessment:
    try:
        return end_to_end_runtime_validation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-runtime-validation/assessments", response_model=list[PipelineAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PipelineAssessment]:
    return end_to_end_runtime_validation_service.list_records(workspace_id)


@router.get("/v1/executive-mt5-runtime-validation/assessments/{record_id}", response_model=PipelineAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PipelineAssessment:
    record = end_to_end_runtime_validation_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pipeline assessment not found")
    return record


@router.post("/v1/executive-mt5-runtime-validation/assessments/{record_id}/execute", response_model=PipelineAssessment)
def execute_assessment(record_id: UUID, request: PipelineExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> PipelineAssessment:
    try:
        return end_to_end_runtime_validation_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-runtime-validation/audit", response_model=list[AuditRecord])
def pipeline_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return end_to_end_runtime_validation_service.audit_records(workspace_id)
