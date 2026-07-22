from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, DynamicRiskCreate, DynamicRiskRecord, RiskAction
from .service import DynamicRiskError, DynamicRiskService

router = APIRouter(prefix="/v1/dynamic-risk", tags=["PHOENIX v21.17"])
service = DynamicRiskService()


@router.get("/status")
def status() -> dict[str, object]:
    return service.status()


@router.post("/records", response_model=DynamicRiskRecord, status_code=201)
def create_record(
    payload: DynamicRiskCreate,
    x_actor: str = Header(default="system", alias="X-Actor"),
) -> DynamicRiskRecord:
    try:
        return service.create(payload, actor=x_actor)
    except DynamicRiskError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DynamicRiskRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[DynamicRiskRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DynamicRiskRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> DynamicRiskRecord:
    try:
        return service.get(workspace_id, record_id)
    except DynamicRiskError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/execute", response_model=DynamicRiskRecord)
def execute_record(
    record_id: str,
    action: RiskAction,
    workspace_id: str = Query(min_length=1),
) -> DynamicRiskRecord:
    try:
        return service.execute(workspace_id, record_id, action)
    except DynamicRiskError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
