from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ReportingActionRequest, ReportingCreate, ReportingGovernanceRecord
from .service import ReportingGovernanceError, service

router = APIRouter(prefix="/v1/reporting-attribution", tags=["PHOENIX v21.45 Reporting Attribution Investor Intelligence"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "reporting-attribution-investor-intelligence", "version": "21.45", "status": "ready"}


@router.post("/records", response_model=ReportingGovernanceRecord)
def create_record(payload: ReportingCreate) -> ReportingGovernanceRecord:
    try:
        return service.create(payload)
    except ReportingGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ReportingGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[ReportingGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=ReportingGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> ReportingGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except ReportingGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ReportingGovernanceRecord)
def act_on_record(record_id: str, request: ReportingActionRequest, x_workspace_id: str = Header(...)) -> ReportingGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except ReportingGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
