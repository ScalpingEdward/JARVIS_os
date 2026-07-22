from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, MarketStructureCreate, MarketStructureRecord, StructureAction
from .service import MarketStructureAnalyzerService, MarketStructureError

router = APIRouter(prefix="/v1/market-structure", tags=["PHOENIX v21.14"])
service = MarketStructureAnalyzerService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=MarketStructureRecord, status_code=201)
def create_record(
    payload: MarketStructureCreate,
    x_actor: str = Header(default="system", alias="X-Actor"),
) -> MarketStructureRecord:
    try:
        return service.create(payload, actor=x_actor)
    except MarketStructureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[MarketStructureRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[MarketStructureRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=MarketStructureRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> MarketStructureRecord:
    try:
        return service.get(workspace_id, record_id)
    except MarketStructureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=MarketStructureRecord)
def execute_record(
    record_id: str,
    action: StructureAction,
    workspace_id: str = Query(min_length=1),
) -> MarketStructureRecord:
    try:
        return service.execute(workspace_id, record_id, action)
    except MarketStructureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
