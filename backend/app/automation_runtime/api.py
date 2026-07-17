from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .models import (
    AutomationJobCreate,
    AutomationJobRecord,
    ConnectorMutation,
    ConnectorRecord,
    ConnectorRegister,
    JobApproval,
    JobCompletion,
    JobState,
    RuntimeStatus,
)
from .service import automation_runtime_service


class HeartbeatPayload(BaseModel):
    healthy: bool = True
    message: str = Field(default="", max_length=500)


router = APIRouter(prefix="/v1/automation-runtime", tags=["automation-runtime"])


@router.get("/status", response_model=RuntimeStatus)
def runtime_status() -> RuntimeStatus:
    return automation_runtime_service.status()


@router.post("/connectors", response_model=ConnectorRecord, status_code=status.HTTP_201_CREATED)
def register_connector(payload: ConnectorRegister) -> ConnectorRecord:
    try:
        return automation_runtime_service.register_connector(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/connectors", response_model=list[ConnectorRecord])
def list_connectors(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ConnectorRecord]:
    return automation_runtime_service.list_connectors(workspace_id)


@router.get("/connectors/{connector_id}", response_model=ConnectorRecord)
def get_connector(
    connector_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ConnectorRecord:
    connector = automation_runtime_service.get_connector(connector_id, workspace_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.post("/connectors/{connector_id}/activate", response_model=ConnectorRecord)
def activate_connector(
    connector_id: UUID,
    payload: ConnectorMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> ConnectorRecord:
    connector = automation_runtime_service.activate_connector(connector_id, workspace_id, requester_id, payload)
    if connector is None:
        raise HTTPException(status_code=404, detail="Owned connector not found")
    return connector


@router.post("/connectors/{connector_id}/disable", response_model=ConnectorRecord)
def disable_connector(
    connector_id: UUID,
    payload: ConnectorMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> ConnectorRecord:
    connector = automation_runtime_service.disable_connector(connector_id, workspace_id, requester_id, payload)
    if connector is None:
        raise HTTPException(status_code=404, detail="Owned connector not found")
    return connector


@router.post("/connectors/{connector_id}/heartbeat", response_model=ConnectorRecord)
def connector_heartbeat(
    connector_id: UUID,
    payload: HeartbeatPayload,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ConnectorRecord:
    connector = automation_runtime_service.heartbeat(connector_id, workspace_id, payload.healthy, payload.message)
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


@router.post("/jobs", response_model=AutomationJobRecord, status_code=status.HTTP_201_CREATED)
def create_job(payload: AutomationJobCreate) -> AutomationJobRecord:
    return automation_runtime_service.create_job(payload)


@router.get("/jobs", response_model=list[AutomationJobRecord])
def list_jobs(
    workspace_id: str = Query(min_length=1, max_length=120),
    state: JobState | None = Query(default=None),
) -> list[AutomationJobRecord]:
    return automation_runtime_service.list_jobs(workspace_id, state)


@router.get("/jobs/{job_id}", response_model=AutomationJobRecord)
def get_job(job_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AutomationJobRecord:
    job = automation_runtime_service.get_job(job_id, workspace_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Automation job not found")
    return job


@router.post("/jobs/{job_id}/approval", response_model=AutomationJobRecord)
def approve_job(
    job_id: UUID,
    payload: JobApproval,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> AutomationJobRecord:
    job = automation_runtime_service.approve_job(job_id, workspace_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Job awaiting approval not found")
    return job


@router.post("/dispatch", response_model=AutomationJobRecord | None)
def dispatch_next(workspace_id: str = Query(min_length=1, max_length=120)) -> AutomationJobRecord | None:
    return automation_runtime_service.dispatch_next(workspace_id)


@router.post("/jobs/{job_id}/complete", response_model=AutomationJobRecord)
def complete_job(
    job_id: UUID,
    payload: JobCompletion,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> AutomationJobRecord:
    job = automation_runtime_service.complete_job(job_id, workspace_id, payload)
    if job is None:
        raise HTTPException(status_code=404, detail="Running automation job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=AutomationJobRecord)
def cancel_job(job_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AutomationJobRecord:
    job = automation_runtime_service.cancel_job(job_id, workspace_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Cancellable automation job not found")
    return job
