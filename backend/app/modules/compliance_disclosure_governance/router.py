from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ComplianceActionRequest, ComplianceCreate, ComplianceGovernanceRecord
from .service import ComplianceGovernanceError, service

router = APIRouter(prefix="/v1/compliance-disclosure", tags=["PHOENIX v21.46 Compliance Disclosure Regulatory Governance"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "compliance-disclosure-regulatory-governance", "version": "21.46", "status": "ready"}


@router.post("/records", response_model=ComplianceGovernanceRecord)
def create_record(payload: ComplianceCreate) -> ComplianceGovernanceRecord:
    try:
        return service.create(payload)
    except ComplianceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ComplianceGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[ComplianceGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=ComplianceGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> ComplianceGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except ComplianceGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ComplianceGovernanceRecord)
def act_on_record(record_id: str, request: ComplianceActionRequest, x_workspace_id: str = Header(...)) -> ComplianceGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except ComplianceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
