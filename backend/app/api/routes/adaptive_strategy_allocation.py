from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.adaptive_strategy_allocation import (
    StrategyAllocationAction,
    StrategyAllocationCreate,
    StrategyAllocationRecord,
)
from app.services.adaptive_strategy_allocation import adaptive_strategy_allocation_service

router = APIRouter(prefix="/v1/adaptive-strategy-allocation", tags=["adaptive-strategy-allocation"])


@router.get("/status")
def status() -> dict:
    return adaptive_strategy_allocation_service.status()


@router.post("/records", response_model=StrategyAllocationRecord)
def create_record(payload: StrategyAllocationCreate) -> StrategyAllocationRecord:
    try:
        return adaptive_strategy_allocation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[StrategyAllocationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[StrategyAllocationRecord]:
    return adaptive_strategy_allocation_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=StrategyAllocationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> StrategyAllocationRecord:
    try:
        return adaptive_strategy_allocation_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=StrategyAllocationRecord)
def apply_action(
    record_id: str,
    payload: StrategyAllocationAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> StrategyAllocationRecord:
    try:
        return adaptive_strategy_allocation_service.act(
            record_id,
            workspace_id,
            payload,
            x_risk_brain_blocked,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return adaptive_strategy_allocation_service.audit(workspace_id)
