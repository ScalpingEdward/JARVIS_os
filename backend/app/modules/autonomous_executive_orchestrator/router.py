from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, status

from .models import AuditEvent, OrchestrationAction, OrchestrationCreate, OrchestrationRecord
from .service import AutonomousExecutiveOrchestratorService, OrchestrationError

router = APIRouter(prefix="/v1/autonomous-executive-orchestrator", tags=["PHOENIX v21.10 Orchestrator"])
service = AutonomousExecutiveOrchestratorService()


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-ID header is required")
    return value


@router.get("/status")
def get_status() -> dict[str, object]:
    return service.status()


@router.post("/workflows", response_model=OrchestrationRecord, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: OrchestrationCreate, x_actor: str = Header(default="system", alias="X-Actor")) -> OrchestrationRecord:
    try:
        return service.create(payload, actor=x_actor)
    except OrchestrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/workflows", response_model=list[OrchestrationRecord])
def list_workflows(x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID")) -> list[OrchestrationRecord]:
    return service.list(_workspace(x_workspace_id))


@router.get("/workflows/{workflow_id}", response_model=OrchestrationRecord)
def get_workflow(workflow_id: str, x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID")) -> OrchestrationRecord:
    try:
        return service.get(_workspace(x_workspace_id), workflow_id)
    except OrchestrationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/execute", response_model=OrchestrationRecord)
def execute_workflow(workflow_id: str, action: OrchestrationAction, x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID")) -> OrchestrationRecord:
    try:
        return service.execute(_workspace(x_workspace_id), workflow_id, action)
    except OrchestrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def get_audit(
    workspace_id: str | None = Query(default=None),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
) -> list[AuditEvent]:
    return service.audit(_workspace(workspace_id or x_workspace_id))
