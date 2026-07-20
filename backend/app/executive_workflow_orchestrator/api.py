from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, WorkflowAssessment, WorkflowAssessmentCreate, WorkflowStatusResponse
from .service import executive_workflow_orchestrator_service

router = APIRouter(tags=["executive-workflow-orchestrator"])
BASE = "/v1/executive-workflow-orchestrator"


@router.get(f"{BASE}/status", response_model=WorkflowStatusResponse)
def workflow_status(workspace_id: str = Query(min_length=1, max_length=100)) -> WorkflowStatusResponse:
    return executive_workflow_orchestrator_service.status(workspace_id)


@router.post(f"{BASE}/workflows", response_model=WorkflowAssessment, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowAssessmentCreate) -> WorkflowAssessment:
    try:
        return executive_workflow_orchestrator_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/workflows", response_model=list[WorkflowAssessment])
def list_workflows(workspace_id: str = Query(min_length=1, max_length=100)) -> list[WorkflowAssessment]:
    return executive_workflow_orchestrator_service.list_assessments(workspace_id)


@router.get(f"{BASE}/workflows/{{assessment_id}}", response_model=WorkflowAssessment)
def get_workflow(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> WorkflowAssessment:
    item = executive_workflow_orchestrator_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Workflow assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def workflow_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_workflow_orchestrator_service.audit(workspace_id)
