from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import (
    ControlledImplementationAudit,
    ControlledImplementationCreate,
    ControlledImplementationRecord,
    ControlledImplementationStatus,
    ImplementationExecuteRequest,
)
from .service import controlled_code_implementation_service

router = APIRouter(prefix="/v1/executive-controlled-code-implementation", tags=["executive-controlled-code-implementation"])


def _workspace(workspace_id: str | None) -> str:
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return workspace_id


@router.get("/status", response_model=ControlledImplementationStatus)
def status(x_workspace_id: str | None = Header(default=None)):
    return controlled_code_implementation_service.status(_workspace(x_workspace_id))


@router.post("/implementations", response_model=ControlledImplementationRecord)
def create(payload: ControlledImplementationCreate, x_workspace_id: str | None = Header(default=None)):
    workspace = _workspace(x_workspace_id)
    if payload.workspace_id != workspace:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return controlled_code_implementation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/implementations", response_model=list[ControlledImplementationRecord])
def list_records(x_workspace_id: str | None = Header(default=None)):
    return controlled_code_implementation_service.list_records(_workspace(x_workspace_id))


@router.get("/implementations/{record_id}", response_model=ControlledImplementationRecord)
def get_record(record_id: UUID, x_workspace_id: str | None = Header(default=None)):
    record = controlled_code_implementation_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="implementation record not found")
    return record


@router.post("/implementations/{record_id}/execute", response_model=ControlledImplementationRecord)
def execute(record_id: UUID, request: ImplementationExecuteRequest, x_workspace_id: str | None = Header(default=None)):
    try:
        return controlled_code_implementation_service.execute(record_id, _workspace(x_workspace_id), request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[ControlledImplementationAudit])
def audit(x_workspace_id: str | None = Header(default=None)):
    return controlled_code_implementation_service.audit_records(_workspace(x_workspace_id))
