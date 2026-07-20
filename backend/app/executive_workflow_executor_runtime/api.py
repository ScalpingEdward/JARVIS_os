from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, WorkflowExecutorAssessment, WorkflowExecutorAssessmentCreate, WorkflowExecutorStatusResponse
from .service import executive_workflow_executor_runtime_service

router = APIRouter(tags=["executive-workflow-executor-runtime"])
BASE = "/v1/executive-workflow-executor-runtime"


@router.get(f"{BASE}/status", response_model=WorkflowExecutorStatusResponse)
def executor_status(workspace_id: str = Query(min_length=1, max_length=100)) -> WorkflowExecutorStatusResponse:
    return executive_workflow_executor_runtime_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=WorkflowExecutorAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: WorkflowExecutorAssessmentCreate) -> WorkflowExecutorAssessment:
    try:
        return executive_workflow_executor_runtime_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[WorkflowExecutorAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[WorkflowExecutorAssessment]:
    return executive_workflow_executor_runtime_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=WorkflowExecutorAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> WorkflowExecutorAssessment:
    item = executive_workflow_executor_runtime_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Workflow executor assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def executor_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_workflow_executor_runtime_service.audit(workspace_id)
