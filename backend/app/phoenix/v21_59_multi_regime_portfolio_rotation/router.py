from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, RotationAction, RotationCreate, RotationRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/portfolio-rotation", tags=["PHOENIX v21.59"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.59",
        "name": "Autonomous Multi-Regime Portfolio Rotation Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct capital movement or trade placement",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=RotationRecord)
def create_record(payload: RotationCreate) -> RotationRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[RotationRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[RotationRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=RotationRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> RotationRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=RotationRecord)
def apply_action(
    record_id: str,
    command: RotationAction,
    x_workspace_id: str = Header(...),
) -> RotationRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
