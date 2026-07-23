from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, SystemicRiskAction, SystemicRiskCreate, SystemicRiskRecord
from .service import GovernanceError, service

router = APIRouter(prefix="/v1/systemic-risk", tags=["PHOENIX v21.60"])


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.60",
        "name": "Autonomous Cross-Portfolio Contagion & Systemic Risk Governance",
        "status": "operational",
        "safety_boundary": "governance-only; no direct trade, fund or broker mutation",
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=SystemicRiskRecord)
def create_record(payload: SystemicRiskCreate) -> SystemicRiskRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[SystemicRiskRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[SystemicRiskRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=SystemicRiskRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> SystemicRiskRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc


@router.post("/records/{record_id}/actions", response_model=SystemicRiskRecord)
def apply_action(
    record_id: str,
    command: SystemicRiskAction,
    x_workspace_id: str = Header(...),
) -> SystemicRiskRecord:
    try:
        return service.act(record_id, x_workspace_id, command)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="record not found") from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return [event for event in service.audit if event.workspace_id == x_workspace_id]
