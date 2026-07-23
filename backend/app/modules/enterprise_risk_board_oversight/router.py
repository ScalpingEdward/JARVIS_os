from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, EnterpriseRiskActionRequest, EnterpriseRiskCreate, EnterpriseRiskGovernanceRecord
from .service import EnterpriseRiskGovernanceError, service

router = APIRouter(prefix="/v1/enterprise-risk-board", tags=["PHOENIX v21.48 Enterprise Risk Board Oversight"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "enterprise-risk-board-oversight", "version": "21.48", "status": "ready"}


@router.post("/records", response_model=EnterpriseRiskGovernanceRecord)
def create_record(payload: EnterpriseRiskCreate) -> EnterpriseRiskGovernanceRecord:
    try:
        return service.create(payload)
    except EnterpriseRiskGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[EnterpriseRiskGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[EnterpriseRiskGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=EnterpriseRiskGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> EnterpriseRiskGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except EnterpriseRiskGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=EnterpriseRiskGovernanceRecord)
def act_on_record(record_id: str, request: EnterpriseRiskActionRequest, x_workspace_id: str = Header(...)) -> EnterpriseRiskGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except EnterpriseRiskGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
