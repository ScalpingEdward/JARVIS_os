from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    NodeApproval,
    NodeCompletion,
    WorkflowActivation,
    WorkflowCreate,
    WorkflowDesignerStatus,
    WorkflowRecord,
    WorkflowRunCreate,
    WorkflowRunRecord,
    WorkflowUpdate,
    WorkflowValidation,
)
from .service import workflow_designer_service


router = APIRouter(prefix="/v1/workflow-designer", tags=["workflow-designer"])


@router.get("/status", response_model=WorkflowDesignerStatus)
def designer_status() -> WorkflowDesignerStatus:
    return workflow_designer_service.status()


@router.post("/workflows", response_model=WorkflowRecord, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate) -> WorkflowRecord:
    return workflow_designer_service.create(payload)


@router.get("/workflows", response_model=list[WorkflowRecord])
def list_workflows(workspace_id: str = Query(min_length=1, max_length=120)) -> list[WorkflowRecord]:
    return workflow_designer_service.list_all(workspace_id)


@router.get("/workflows/{workflow_id}", response_model=WorkflowRecord)
def get_workflow(
    workflow_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRecord:
    record = workflow_designer_service.get(workflow_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return record


@router.patch("/workflows/{workflow_id}", response_model=WorkflowRecord)
def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRecord:
    record = workflow_designer_service.update(workflow_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned workflow not found")
    return record


@router.post("/workflows/{workflow_id}/validate", response_model=WorkflowValidation)
def validate_workflow(
    workflow_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowValidation:
    validation = workflow_designer_service.validate(workflow_id, workspace_id)
    if validation is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return validation


@router.post("/workflows/{workflow_id}/activate", response_model=WorkflowRecord)
def activate_workflow(
    workflow_id: UUID,
    payload: WorkflowActivation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRecord:
    record = workflow_designer_service.activate(workflow_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned workflow not found")
    return record


@router.post("/workflows/{workflow_id}/archive", response_model=WorkflowRecord)
def archive_workflow(
    workflow_id: UUID,
    payload: WorkflowActivation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRecord:
    record = workflow_designer_service.archive(workflow_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned workflow not found")
    return record


@router.post("/workflows/{workflow_id}/runs", response_model=WorkflowRunRecord, status_code=status.HTTP_201_CREATED)
def start_run(workflow_id: UUID, payload: WorkflowRunCreate) -> WorkflowRunRecord:
    run = workflow_designer_service.start_run(workflow_id, payload)
    if run is None:
        raise HTTPException(status_code=409, detail="Active valid workflow not found")
    return run


@router.get("/runs", response_model=list[WorkflowRunRecord])
def list_runs(workspace_id: str = Query(min_length=1, max_length=120)) -> list[WorkflowRunRecord]:
    return workflow_designer_service.list_runs(workspace_id)


@router.get("/runs/{run_id}", response_model=WorkflowRunRecord)
def get_run(
    run_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRunRecord:
    run = workflow_designer_service.get_run(run_id, workspace_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.post("/runs/{run_id}/nodes/{node_key}/complete", response_model=WorkflowRunRecord)
def complete_node(
    run_id: UUID,
    node_key: str,
    payload: NodeCompletion,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRunRecord:
    run = workflow_designer_service.complete_node(run_id, node_key, workspace_id, payload)
    if run is None:
        raise HTTPException(status_code=404, detail="Runnable workflow node not found")
    return run


@router.post("/runs/{run_id}/nodes/{node_key}/approval", response_model=WorkflowRunRecord)
def approve_node(
    run_id: UUID,
    node_key: str,
    payload: NodeApproval,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRunRecord:
    run = workflow_designer_service.approve_node(run_id, node_key, workspace_id, payload)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow approval node not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=WorkflowRunRecord)
def cancel_run(
    run_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> WorkflowRunRecord:
    run = workflow_designer_service.cancel_run(run_id, workspace_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run
