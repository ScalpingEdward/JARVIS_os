from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AdapterExecutionAssessment, AdapterExecutionAssessmentCreate, AdapterExecutionStatusResponse, AuditRecord
from .service import executive_vision_adapter_execution_service

router = APIRouter(tags=["executive-vision-adapter-execution"])
BASE = "/v1/executive-vision-adapter-execution"


@router.get(f"{BASE}/status", response_model=AdapterExecutionStatusResponse)
def execution_status(workspace_id: str = Query(min_length=1, max_length=100)) -> AdapterExecutionStatusResponse:
    return executive_vision_adapter_execution_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=AdapterExecutionAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AdapterExecutionAssessmentCreate) -> AdapterExecutionAssessment:
    try:
        return executive_vision_adapter_execution_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[AdapterExecutionAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AdapterExecutionAssessment]:
    return executive_vision_adapter_execution_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=AdapterExecutionAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> AdapterExecutionAssessment:
    item = executive_vision_adapter_execution_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision adapter execution assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def execution_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_vision_adapter_execution_service.audit(workspace_id)
