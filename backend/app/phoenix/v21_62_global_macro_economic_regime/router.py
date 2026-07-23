from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, MacroAction, MacroCreate, MacroRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/macro-governance", tags=["PHOENIX v21.62"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.62",
        "name": "Autonomous Global Macro Intelligence & Economic Regime Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct trade placement, allocation mutation or broker execution",
        "risk_brain_authoritative": True,
        "human_approval_required": True,
    }


@router.post("/records", response_model=MacroRecord)
def create_record(payload: MacroCreate) -> MacroRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[MacroRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[MacroRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=MacroRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> MacroRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=MacroRecord)
def apply_action(record_id: str, command: MacroAction, x_workspace_id: str = Header(...)) -> MacroRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
