from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from .models import (
    BudgetAllocationAudit,
    BudgetAllocationCreate,
    BudgetAllocationExecuteRequest,
    BudgetAllocationRecord,
    BudgetAllocationStatus,
)
from .service import budget_allocation_service

router = APIRouter(prefix="/v1/budget-allocation", tags=["budget-allocation"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status", response_model=BudgetAllocationStatus)
def status(x_workspace_id: str | None = Header(default=None)) -> BudgetAllocationStatus:
    return budget_allocation_service.status(_workspace(x_workspace_id))


@router.post("/records", response_model=BudgetAllocationRecord, status_code=201)
def create_record(
    payload: BudgetAllocationCreate,
    x_workspace_id: str | None = Header(default=None),
) -> BudgetAllocationRecord:
    workspace_id = _workspace(x_workspace_id)
    if payload.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return budget_allocation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[BudgetAllocationRecord])
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[BudgetAllocationRecord]:
    return budget_allocation_service.list_records(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=BudgetAllocationRecord)
def get_record(
    record_id: UUID,
    x_workspace_id: str | None = Header(default=None),
) -> BudgetAllocationRecord:
    record = budget_allocation_service.get(record_id, _workspace(x_workspace_id))
    if record is None:
        raise HTTPException(status_code=404, detail="budget allocation record not found")
    return record


@router.post("/records/{record_id}/execute", response_model=BudgetAllocationRecord)
def execute_record(
    record_id: UUID,
    payload: BudgetAllocationExecuteRequest,
    x_workspace_id: str | None = Header(default=None),
) -> BudgetAllocationRecord:
    try:
        return budget_allocation_service.execute(record_id, _workspace(x_workspace_id), payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[BudgetAllocationAudit])
def audit(x_workspace_id: str | None = Header(default=None)) -> list[BudgetAllocationAudit]:
    return budget_allocation_service.audit_records(_workspace(x_workspace_id))
