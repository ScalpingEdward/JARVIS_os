from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, SetupAction, TradeSetupCreate, TradeSetupRecord
from .service import TradeSetupError, TradeSetupQualificationService

router = APIRouter(prefix="/v1/trade-setups", tags=["PHOENIX v21.15"])
service = TradeSetupQualificationService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=TradeSetupRecord, status_code=201)
def create_record(
    payload: TradeSetupCreate,
    x_actor: str = Header(default="system", alias="X-Actor"),
) -> TradeSetupRecord:
    try:
        return service.create(payload, actor=x_actor)
    except TradeSetupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TradeSetupRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[TradeSetupRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=TradeSetupRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> TradeSetupRecord:
    try:
        return service.get(workspace_id, record_id)
    except TradeSetupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=TradeSetupRecord)
def execute_record(
    record_id: str,
    action: SetupAction,
    workspace_id: str = Query(min_length=1),
) -> TradeSetupRecord:
    try:
        return service.execute(workspace_id, record_id, action)
    except TradeSetupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
