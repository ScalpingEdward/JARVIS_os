from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEntry, StrategicRiskCreate, StrategicRiskExecute, StrategicRiskRecord
from .service import service

router = APIRouter(prefix="/v1/strategic-risks", tags=["PHOENIX v21.07"])


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=StrategicRiskRecord, status_code=201)
def create_record(
    payload: StrategicRiskCreate,
    x_actor: str = Header(default="system"),
) -> StrategicRiskRecord:
    try:
        return service.create(payload, actor=x_actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[StrategicRiskRecord])
def list_records(workspace_id: str = Query(min_length=2)) -> list[StrategicRiskRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=StrategicRiskRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=2)) -> StrategicRiskRecord:
    try:
        return service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=StrategicRiskRecord)
def execute_record(
    record_id: str,
    command: StrategicRiskExecute,
    workspace_id: str = Query(min_length=2),
) -> StrategicRiskRecord:
    try:
        return service.execute(record_id, workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEntry])
def audit(workspace_id: str = Query(min_length=2)) -> list[AuditEntry]:
    return service.audit(workspace_id)
