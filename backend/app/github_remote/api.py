from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import RemoteExecutionResponse
from .service import GitHubRemoteError, github_remote_executor

router = APIRouter(prefix="/v1/github-remote", tags=["github-remote"])


def _call(operation):
    try:
        return operation()
    except GitHubRemoteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
def status() -> dict[str, bool]:
    return {"available": github_remote_executor.available(), "automatic_merge": False}


@router.post("/workspaces/{workspace_id}/execute", response_model=RemoteExecutionResponse)
def execute(workspace_id: UUID) -> RemoteExecutionResponse:
    return _call(lambda: github_remote_executor.execute(workspace_id))


@router.post("/workspaces/{workspace_id}/sync-ci", response_model=RemoteExecutionResponse)
def sync_ci(workspace_id: UUID) -> RemoteExecutionResponse:
    return _call(lambda: github_remote_executor.sync_ci(workspace_id))
