from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import BridgeApproval, BridgeCreate, BridgeListResponse, BridgeRecord, BridgeStatus
from .service import goal_execution_service

router = APIRouter(prefix="/v1/goal-execution", tags=["goal-execution"])


@router.get("/status", response_model=BridgeStatus)
def bridge_status() -> BridgeStatus:
    return goal_execution_service.status()


@router.post("", response_model=BridgeRecord, status_code=status.HTTP_201_CREATED)
def create_bridge(payload: BridgeCreate) -> BridgeRecord:
    try:
        return goal_execution_service.create(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=BridgeListResponse)
def list_bridges() -> BridgeListResponse:
    items = goal_execution_service.list_all()
    return BridgeListResponse(items=items, count=len(items))


@router.get("/{bridge_id}", response_model=BridgeRecord)
def get_bridge(bridge_id: UUID) -> BridgeRecord:
    record = goal_execution_service.get(bridge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution bridge not found")
    return record


@router.post("/{bridge_id}/approve", response_model=BridgeRecord)
def approve_bridge(bridge_id: UUID, payload: BridgeApproval) -> BridgeRecord:
    try:
        record = goal_execution_service.approve(bridge_id, payload)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Execution bridge not found")
    return record


@router.post("/{bridge_id}/sync", response_model=BridgeRecord)
def sync_bridge(bridge_id: UUID) -> BridgeRecord:
    record = goal_execution_service.sync(bridge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution bridge not found")
    return record
