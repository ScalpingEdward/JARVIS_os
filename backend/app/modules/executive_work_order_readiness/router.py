from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import WorkOrderReadinessCreate, WorkOrderReadinessExecuteRequest
from .service import work_order_readiness_service

router = APIRouter(prefix="/v1/executive-work-order-readiness", tags=["executive-work-order-readiness"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def status(x_workspace_id: str | None = Header(default=None)):
    return work_order_readiness_service.status(_workspace(x_workspace_id))


@router.post("/records")
def create_record(payload: WorkOrderReadinessCreate, x_workspace_id: str | None = Header(default=None)):
    workspace_id = _workspace(x_workspace_id)
    if payload.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return work_order_readiness_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def list_records(x_workspace_id: str | None = Header(default=None)):
    return work_order_readiness_service.list_records(_workspace(x_workspace_id))


@router.get("/records/{record_id}")
def get_record(record_id: UUID, x_workspace_id: str | None = Header(default=None)):
    record = work_order_readiness_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    return record


@router.post("/records/{record_id}/execute")
def execute_record(record_id: UUID, request: WorkOrderReadinessExecuteRequest, x_workspace_id: str | None = Header(default=None)):
    try:
        return work_order_readiness_service.execute(record_id, _workspace(x_workspace_id), request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)):
    return work_order_readiness_service.audit_records(_workspace(x_workspace_id))
