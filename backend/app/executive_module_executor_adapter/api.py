from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ModuleExecutorAssessment, ModuleExecutorAssessmentCreate, ModuleExecutorStatusResponse
from .service import executive_module_executor_adapter_service

router = APIRouter(tags=["executive-module-executor-adapter"])
BASE = "/v1/executive-module-executor-adapter"


@router.get(f"{BASE}/status", response_model=ModuleExecutorStatusResponse)
def module_executor_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ModuleExecutorStatusResponse:
    return executive_module_executor_adapter_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=ModuleExecutorAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ModuleExecutorAssessmentCreate) -> ModuleExecutorAssessment:
    try:
        return executive_module_executor_adapter_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[ModuleExecutorAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ModuleExecutorAssessment]:
    return executive_module_executor_adapter_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=ModuleExecutorAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ModuleExecutorAssessment:
    item = executive_module_executor_adapter_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Module executor assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def module_executor_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_module_executor_adapter_service.audit(workspace_id)
