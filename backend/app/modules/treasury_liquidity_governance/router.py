from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, TreasuryActionRequest, TreasuryCreate, TreasuryGovernanceRecord
from .service import TreasuryGovernanceError, service

router = APIRouter(prefix="/v1/treasury-liquidity", tags=["PHOENIX v21.42 Treasury Liquidity Governance"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "treasury-liquidity-governance", "version": "21.42", "status": "ready"}


@router.post("/records", response_model=TreasuryGovernanceRecord)
def create_record(payload: TreasuryCreate) -> TreasuryGovernanceRecord:
    try:
        return service.create(payload)
    except TreasuryGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TreasuryGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[TreasuryGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=TreasuryGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> TreasuryGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except TreasuryGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=TreasuryGovernanceRecord)
def act_on_record(record_id: str, request: TreasuryActionRequest, x_workspace_id: str = Header(...)) -> TreasuryGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except TreasuryGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
