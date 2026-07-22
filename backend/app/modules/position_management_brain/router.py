from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, PositionAction, PositionCreate, PositionRecord
from .service import PositionManagementError, PositionManagementService

router = APIRouter(prefix="/v1/position-management", tags=["PHOENIX v21.16"])
service = PositionManagementService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=PositionRecord, status_code=201)
def create_record(payload: PositionCreate, x_actor: str = Header(default="system", alias="X-Actor")) -> PositionRecord:
    try:
        return service.create(payload, actor=x_actor)
    except PositionManagementError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[PositionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[PositionRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=PositionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> PositionRecord:
    try:
        return service.get(workspace_id, record_id)
    except PositionManagementError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=PositionRecord)
def execute_record(record_id: str, action: PositionAction, workspace_id: str = Query(min_length=1)) -> PositionRecord:
    try:
        return service.execute(workspace_id, record_id, action)
    except PositionManagementError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
