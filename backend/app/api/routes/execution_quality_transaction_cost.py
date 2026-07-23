from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.execution_quality_transaction_cost import (
    ExecutionAction,
    ExecutionRecord,
    ExecutionRecordCreate,
)
from app.services.execution_quality_transaction_cost import execution_quality_service

router = APIRouter(prefix="/v1/execution-quality", tags=["execution-quality"])


@router.get("/status")
def status() -> dict:
    return execution_quality_service.status()


@router.post("/records", response_model=ExecutionRecord)
def create_record(payload: ExecutionRecordCreate) -> ExecutionRecord:
    try:
        return execution_quality_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ExecutionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ExecutionRecord]:
    return execution_quality_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ExecutionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ExecutionRecord:
    try:
        return execution_quality_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ExecutionRecord)
def apply_action(
    record_id: str,
    payload: ExecutionAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> ExecutionRecord:
    try:
        return execution_quality_service.act(record_id, workspace_id, payload, x_risk_brain_blocked)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return execution_quality_service.audit(workspace_id)
