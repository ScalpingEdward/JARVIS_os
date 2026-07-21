from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import (
    ImprovementHandoffAudit,
    ImprovementHandoffCreate,
    ImprovementHandoffExecuteRequest,
    ImprovementHandoffRecord,
    ImprovementHandoffStatus,
)
from .service import improvement_handoff_service

router = APIRouter(
    prefix="/v1/executive-improvement-handoff",
    tags=["executive-improvement-handoff"],
)


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status", response_model=ImprovementHandoffStatus)
def status(x_workspace_id: str | None = Header(default=None)):
    return improvement_handoff_service.status(_workspace(x_workspace_id))


@router.post("/records", response_model=ImprovementHandoffRecord, status_code=201)
def create_record(payload: ImprovementHandoffCreate):
    try:
        return improvement_handoff_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ImprovementHandoffRecord])
def list_records(x_workspace_id: str | None = Header(default=None)):
    return improvement_handoff_service.list_records(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=ImprovementHandoffRecord)
def get_record(record_id: UUID, x_workspace_id: str | None = Header(default=None)):
    record = improvement_handoff_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="improvement handoff record not found")
    return record


@router.post("/records/{record_id}/execute", response_model=ImprovementHandoffRecord)
def execute_record(
    record_id: UUID,
    request: ImprovementHandoffExecuteRequest,
    x_workspace_id: str | None = Header(default=None),
):
    try:
        return improvement_handoff_service.execute(record_id, _workspace(x_workspace_id), request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[ImprovementHandoffAudit])
def audit(x_workspace_id: str | None = Header(default=None)):
    return improvement_handoff_service.audit_records(_workspace(x_workspace_id))
