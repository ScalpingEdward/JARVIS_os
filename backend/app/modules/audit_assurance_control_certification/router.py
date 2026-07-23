from fastapi import APIRouter, Header, HTTPException

from .models import AssuranceActionRequest, AssuranceCreate, AssuranceGovernanceRecord, AuditEvent
from .service import AssuranceGovernanceError, service

router = APIRouter(prefix="/v1/audit-assurance", tags=["PHOENIX v21.47 Audit Assurance Control Certification"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "audit-assurance-control-certification", "version": "21.47", "status": "ready"}


@router.post("/records", response_model=AssuranceGovernanceRecord)
def create_record(payload: AssuranceCreate) -> AssuranceGovernanceRecord:
    try:
        return service.create(payload)
    except AssuranceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AssuranceGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[AssuranceGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=AssuranceGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> AssuranceGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except AssuranceGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AssuranceGovernanceRecord)
def act_on_record(record_id: str, request: AssuranceActionRequest, x_workspace_id: str = Header(...)) -> AssuranceGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except AssuranceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
