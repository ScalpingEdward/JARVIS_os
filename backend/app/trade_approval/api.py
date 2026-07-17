from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    KillSwitchState,
    KillSwitchUpdate,
    TradeApprovalCreate,
    TradeApprovalRecord,
    TradeApprovalStatus,
)
from .service import trade_approval_service


router = APIRouter(prefix="/v1/trade-approval", tags=["trade-approval"])


@router.get("/status", response_model=TradeApprovalStatus)
def approval_status() -> TradeApprovalStatus:
    return trade_approval_service.status()


@router.post("/evaluations", response_model=TradeApprovalRecord, status_code=status.HTTP_201_CREATED)
def evaluate_trade(payload: TradeApprovalCreate) -> TradeApprovalRecord:
    return trade_approval_service.evaluate(payload)


@router.get("/evaluations", response_model=list[TradeApprovalRecord])
def list_evaluations() -> list[TradeApprovalRecord]:
    return trade_approval_service.list_all()


@router.get("/evaluations/{record_id}", response_model=TradeApprovalRecord)
def get_evaluation(record_id: UUID) -> TradeApprovalRecord:
    record = trade_approval_service.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Trade approval record not found")
    return record


@router.get("/kill-switch", response_model=KillSwitchState)
def get_kill_switch() -> KillSwitchState:
    return trade_approval_service.kill_switch()


@router.put("/kill-switch", response_model=KillSwitchState)
def update_kill_switch(payload: KillSwitchUpdate) -> KillSwitchState:
    return trade_approval_service.update_kill_switch(payload)
