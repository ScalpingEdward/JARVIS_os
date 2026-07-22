from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, JournalAction, TradeJournalCreate, TradeJournalRecord
from .service import JournalError, TradeJournalIntelligenceService

router = APIRouter(prefix="/v1/trade-journal", tags=["PHOENIX v21.19 Trade Journal Intelligence"])
service = TradeJournalIntelligenceService()


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.19 Trade Journal Intelligence",
        "status": "operational",
        "live_execution": False,
        "human_approval_required": True,
    }


@router.post("/records", response_model=TradeJournalRecord)
def create_record(payload: TradeJournalCreate) -> TradeJournalRecord:
    try:
        return service.create(payload)
    except JournalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TradeJournalRecord])
def list_records(workspace_id: str = Query(..., min_length=1)) -> list[TradeJournalRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=TradeJournalRecord)
def get_record(record_id: str, workspace_id: str = Query(..., min_length=1)) -> TradeJournalRecord:
    try:
        return service.get(workspace_id, record_id)
    except JournalError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=TradeJournalRecord)
def apply_action(
    record_id: str,
    payload: JournalAction,
    workspace_id: str = Query(..., min_length=1),
) -> TradeJournalRecord:
    try:
        return service.act(workspace_id, record_id, payload)
    except JournalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)


@router.get("/summary")
def summary(workspace_id: str = Query(..., min_length=1)) -> dict:
    return service.summary(workspace_id)
