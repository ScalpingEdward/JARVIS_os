from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, StrategyFactoryActionRequest, StrategyFactoryCreate, StrategyFactoryRecord
from .service import StrategyFactoryError, service

router = APIRouter(
    prefix="/v1/strategy-factory",
    tags=["PHOENIX v21.54 Strategy Factory Alpha Lifecycle"],
)


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "module": "strategy-factory-alpha-lifecycle-governance",
        "version": "21.54",
        "status": "ready",
    }


@router.post("/records", response_model=StrategyFactoryRecord)
def create_record(payload: StrategyFactoryCreate) -> StrategyFactoryRecord:
    try:
        return service.create(payload)
    except StrategyFactoryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[StrategyFactoryRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[StrategyFactoryRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=StrategyFactoryRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> StrategyFactoryRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except StrategyFactoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=StrategyFactoryRecord)
def act_on_record(
    record_id: str,
    request: StrategyFactoryActionRequest,
    x_workspace_id: str = Header(...),
) -> StrategyFactoryRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except StrategyFactoryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
