from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, CrisisActionRequest, CrisisCreate, CrisisGovernanceRecord
from .service import CrisisGovernanceError, service

router = APIRouter(prefix="/v1/crisis-command", tags=["PHOENIX v21.49 Crisis Command Resolution Continuity"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "crisis-command-resolution-continuity", "version": "21.49", "status": "ready"}


@router.post("/records", response_model=CrisisGovernanceRecord)
def create_record(payload: CrisisCreate) -> CrisisGovernanceRecord:
    try:
        return service.create(payload)
    except CrisisGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CrisisGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[CrisisGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=CrisisGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> CrisisGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except CrisisGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CrisisGovernanceRecord)
def act_on_record(record_id: str, request: CrisisActionRequest, x_workspace_id: str = Header(...)) -> CrisisGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except CrisisGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
