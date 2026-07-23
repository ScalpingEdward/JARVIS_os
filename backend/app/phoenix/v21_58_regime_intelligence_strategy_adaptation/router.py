from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, RegimeAction, RegimeCreate, RegimeRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/regime-intelligence", tags=["PHOENIX v21.58"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.58",
        "name": "Autonomous Regime Intelligence & Strategy Adaptation Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct strategy deployment, trade placement or broker mutation",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=RegimeRecord)
def create_record(payload: RegimeCreate) -> RegimeRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[RegimeRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[RegimeRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=RegimeRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> RegimeRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=RegimeRecord)
def apply_action(record_id: str, command: RegimeAction, x_workspace_id: str = Header(...)) -> RegimeRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
