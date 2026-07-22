from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, ScenarioAction, TradeScenarioCreate, TradeScenarioRecord
from .service import TradeScenarioError, TradeScenarioVisualizerService

router = APIRouter(prefix="/v1/trade-scenarios", tags=["trade-scenarios"])
service = TradeScenarioVisualizerService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=TradeScenarioRecord)
def create_record(
    payload: TradeScenarioCreate,
    x_actor: str = Header(default="system"),
) -> TradeScenarioRecord:
    try:
        return service.create(payload, actor=x_actor)
    except TradeScenarioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TradeScenarioRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[TradeScenarioRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=TradeScenarioRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> TradeScenarioRecord:
    try:
        return service.get(workspace_id, record_id)
    except TradeScenarioError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=TradeScenarioRecord)
def execute_record(
    record_id: str,
    action: ScenarioAction,
    workspace_id: str = Query(min_length=1),
) -> TradeScenarioRecord:
    try:
        return service.execute(workspace_id, record_id, action)
    except TradeScenarioError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
