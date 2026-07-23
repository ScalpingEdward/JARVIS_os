from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, SettlementActionRequest, SettlementCreate, SettlementGovernanceRecord
from .service import SettlementGovernanceError, service

router = APIRouter(prefix="/v1/settlement-custody", tags=["PHOENIX v21.43 Settlement Custody Reconciliation"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "settlement-custody-reconciliation", "version": "21.43", "status": "ready"}


@router.post("/records", response_model=SettlementGovernanceRecord)
def create_record(payload: SettlementCreate) -> SettlementGovernanceRecord:
    try:
        return service.create(payload)
    except SettlementGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[SettlementGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[SettlementGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=SettlementGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> SettlementGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except SettlementGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=SettlementGovernanceRecord)
def act_on_record(record_id: str, request: SettlementActionRequest, x_workspace_id: str = Header(...)) -> SettlementGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except SettlementGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
