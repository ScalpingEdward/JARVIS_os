from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, CloseActionRequest, FinancialCloseCreate, FinancialCloseRecord
from .service import FinancialCloseError, service

router = APIRouter(prefix="/v1/financial-close-nav", tags=["PHOENIX v21.44 Financial Close NAV Performance"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "financial-close-nav-performance", "version": "21.44", "status": "ready"}


@router.post("/records", response_model=FinancialCloseRecord)
def create_record(payload: FinancialCloseCreate) -> FinancialCloseRecord:
    try:
        return service.create(payload)
    except FinancialCloseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[FinancialCloseRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[FinancialCloseRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=FinancialCloseRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> FinancialCloseRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except FinancialCloseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=FinancialCloseRecord)
def act_on_record(record_id: str, request: CloseActionRequest, x_workspace_id: str = Header(...)) -> FinancialCloseRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except FinancialCloseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
