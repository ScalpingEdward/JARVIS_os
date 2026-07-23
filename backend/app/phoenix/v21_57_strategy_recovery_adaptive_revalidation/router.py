from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, RecoveryAction, RecoveryCreate, RecoveryRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/strategy-recovery", tags=["PHOENIX v21.57"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.57",
        "name": "Autonomous Strategy Recovery & Adaptive Revalidation Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct strategy deployment, trade placement or fund movement",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=RecoveryRecord)
def create_record(payload: RecoveryCreate) -> RecoveryRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[RecoveryRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[RecoveryRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=RecoveryRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> RecoveryRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=RecoveryRecord)
def apply_action(
    record_id: str,
    command: RecoveryAction,
    x_workspace_id: str = Header(...),
) -> RecoveryRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
