from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    InstitutionalTradeJournalAudit,
    InstitutionalTradeJournalCreate,
    InstitutionalTradeJournalRecord,
    InstitutionalTradeJournalStatus,
    TradeJournalExecuteRequest,
)
from .service import institutional_trade_journal_service

router = APIRouter(tags=["executive-institutional-trade-journal"])


@router.get("/v1/executive-trade-journal/status", response_model=InstitutionalTradeJournalStatus)
def journal_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return institutional_trade_journal_service.status(workspace_id)


@router.post("/v1/executive-trade-journal/records", response_model=InstitutionalTradeJournalRecord, status_code=status.HTTP_201_CREATED)
def create_journal(payload: InstitutionalTradeJournalCreate):
    try:
        return institutional_trade_journal_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trade-journal/records", response_model=list[InstitutionalTradeJournalRecord])
def list_journals(workspace_id: str = Query(min_length=1, max_length=100)):
    return institutional_trade_journal_service.list_records(workspace_id)


@router.get("/v1/executive-trade-journal/records/{record_id}", response_model=InstitutionalTradeJournalRecord)
def get_journal(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = institutional_trade_journal_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="journal record not found")
    return record


@router.post("/v1/executive-trade-journal/records/{record_id}/execute", response_model=InstitutionalTradeJournalRecord)
def execute_journal(record_id: UUID, request: TradeJournalExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return institutional_trade_journal_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trade-journal/audit", response_model=list[InstitutionalTradeJournalAudit])
def journal_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return institutional_trade_journal_service.audit_records(workspace_id)
