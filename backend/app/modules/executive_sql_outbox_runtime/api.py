from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, SqlOutboxRuntimeAssessment, SqlOutboxRuntimeAssessmentCreate, SqlOutboxRuntimeStatusResponse
from .service import executive_sql_outbox_runtime_service

router = APIRouter(tags=["executive-sql-outbox-runtime"])
BASE = "/v1/executive-sql-outbox-runtime"


@router.get(f"{BASE}/status", response_model=SqlOutboxRuntimeStatusResponse)
def runtime_status(workspace_id: str = Query(min_length=1, max_length=100)) -> SqlOutboxRuntimeStatusResponse:
    return executive_sql_outbox_runtime_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=SqlOutboxRuntimeAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: SqlOutboxRuntimeAssessmentCreate) -> SqlOutboxRuntimeAssessment:
    try:
        return executive_sql_outbox_runtime_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[SqlOutboxRuntimeAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[SqlOutboxRuntimeAssessment]:
    return executive_sql_outbox_runtime_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=SqlOutboxRuntimeAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> SqlOutboxRuntimeAssessment:
    item = executive_sql_outbox_runtime_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="SQL outbox runtime assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def runtime_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_sql_outbox_runtime_service.audit(workspace_id)
