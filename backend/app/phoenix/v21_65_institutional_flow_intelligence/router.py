from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, FlowAction, FlowCreate, FlowRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/institutional-flow", tags=["PHOENIX v21.65"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.65",
        "name": "Autonomous Institutional Flow Intelligence Governance",
        "status": "operational",
        "safety_boundary": "intelligence and governance only; no direct trade, allocation, fund or broker mutation",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=FlowRecord)
def create_record(payload: FlowCreate) -> FlowRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[FlowRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[FlowRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=FlowRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> FlowRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=FlowRecord)
def apply_action(record_id: str, command: FlowAction, x_workspace_id: str = Header(...)) -> FlowRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
