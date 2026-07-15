from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import (
    WorkspaceCreate,
    WorkspaceDecision,
    WorkspaceList,
    WorkspacePatch,
    WorkspaceRecord,
    WorkspaceResult,
)
from .service import WorkspaceError, workspace_executor_service

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


def _call(operation):
    try:
        return operation()
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=WorkspaceRecord)
def create_workspace(payload: WorkspaceCreate) -> WorkspaceRecord:
    return workspace_executor_service.create(payload)


@router.get("", response_model=WorkspaceList)
def list_workspaces() -> WorkspaceList:
    items = workspace_executor_service.list_all()
    return WorkspaceList(items=items, count=len(items))


@router.get("/{workspace_id}", response_model=WorkspaceRecord)
def get_workspace(workspace_id: UUID) -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.get(workspace_id))


@router.post("/{workspace_id}/approval", response_model=WorkspaceRecord)
def approve_workspace(workspace_id: UUID, payload: WorkspaceDecision) -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.decide(workspace_id, payload))


@router.post("/{workspace_id}/patch", response_model=WorkspaceRecord)
def attach_patch(workspace_id: UUID, payload: WorkspacePatch) -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.attach_patch(workspace_id, payload))


@router.post("/{workspace_id}/branch-created", response_model=WorkspaceRecord)
def mark_branch_created(workspace_id: UUID) -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.mark_branch_created(workspace_id))


@router.post("/{workspace_id}/tests/{passed}", response_model=WorkspaceRecord)
def record_tests(workspace_id: UUID, passed: bool, details: str = "") -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.record_tests(workspace_id, passed, details))


@router.post("/{workspace_id}/pull-request", response_model=WorkspaceRecord)
def record_pull_request(workspace_id: UUID, number: int, url: str, commit_sha: str) -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.record_pull_request(workspace_id, number, url, commit_sha))


@router.post("/{workspace_id}/ci/{passed}", response_model=WorkspaceRecord)
def record_ci(workspace_id: UUID, passed: bool, details: str = "") -> WorkspaceRecord:
    return _call(lambda: workspace_executor_service.record_ci(workspace_id, passed, details))


@router.post("/{workspace_id}/review", response_model=WorkspaceResult)
def record_review(workspace_id: UUID, payload: WorkspaceDecision) -> WorkspaceResult:
    return _call(lambda: workspace_executor_service.record_review(workspace_id, payload))
