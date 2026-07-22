from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ReconciliationAction, ReconciliationCreate, ReconciliationRecord
from .service import BrokerStateReconciliationError, service

router = APIRouter(prefix="/v1/broker-state-reconciliation", tags=["broker-state-reconciliation"])


def _workspace(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")
    return value


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "PHOENIX v21.25", "status": "ready"}


@router.post("/reconciliations", response_model=ReconciliationRecord)
def create(payload: ReconciliationCreate) -> ReconciliationRecord:
    try:
        return service.create(payload)
    except BrokerStateReconciliationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/reconciliations", response_model=list[ReconciliationRecord])
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[ReconciliationRecord]:
    return service.list(_workspace(x_workspace_id))


@router.get("/reconciliations/{record_id}", response_model=ReconciliationRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)) -> ReconciliationRecord:
    try:
        return service.get(record_id, _workspace(x_workspace_id))
    except BrokerStateReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reconciliations/{record_id}/actions", response_model=ReconciliationRecord)
def act(record_id: str, action: ReconciliationAction, x_workspace_id: str | None = Header(default=None)) -> ReconciliationRecord:
    try:
        return service.act(record_id, _workspace(x_workspace_id), action)
    except BrokerStateReconciliationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str | None = Header(default=None)) -> list[AuditEvent]:
    return service.audit(_workspace(x_workspace_id))
