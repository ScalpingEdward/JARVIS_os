from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.capital_allocation_optimization import (
    AllocationAction,
    AllocationRecord,
    AllocationRecordCreate,
)
from app.services.capital_allocation_optimization import capital_allocation_service

router = APIRouter(prefix="/v1/capital-allocation", tags=["capital-allocation"])


@router.get("/status")
def status() -> dict:
    return capital_allocation_service.status()


@router.post("/records", response_model=AllocationRecord)
def create_record(payload: AllocationRecordCreate) -> AllocationRecord:
    try:
        return capital_allocation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AllocationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AllocationRecord]:
    return capital_allocation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AllocationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AllocationRecord:
    try:
        return capital_allocation_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AllocationRecord)
def apply_action(
    record_id: str,
    payload: AllocationAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> AllocationRecord:
    try:
        return capital_allocation_service.act(record_id, workspace_id, payload, x_risk_brain_blocked)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return capital_allocation_service.audit(workspace_id)
