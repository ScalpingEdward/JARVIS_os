from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, LiveAlphaAction, LiveAlphaCreate, LiveAlphaRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/live-alpha", tags=["PHOENIX v21.56"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.56",
        "name": "Autonomous Live Alpha Performance & Capital Preservation Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct trade placement or broker mutation",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=LiveAlphaRecord)
def create_record(payload: LiveAlphaCreate) -> LiveAlphaRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[LiveAlphaRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[LiveAlphaRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=LiveAlphaRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> LiveAlphaRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=LiveAlphaRecord)
def apply_action(record_id: str, command: LiveAlphaAction, x_workspace_id: str = Header(...)) -> LiveAlphaRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
