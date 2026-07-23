from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, MaturityActionRequest, MaturityCreate, MaturityGovernanceRecord
from .service import MaturityGovernanceError, service

router = APIRouter(
    prefix="/v1/operational-maturity",
    tags=["PHOENIX v21.51 Operational Maturity Continuous Improvement"],
)


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "module": "operational-maturity-continuous-improvement",
        "version": "21.51",
        "status": "ready",
    }


@router.post("/records", response_model=MaturityGovernanceRecord)
def create_record(payload: MaturityCreate) -> MaturityGovernanceRecord:
    try:
        return service.create(payload)
    except MaturityGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[MaturityGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[MaturityGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=MaturityGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> MaturityGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except MaturityGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=MaturityGovernanceRecord)
def act_on_record(
    record_id: str,
    request: MaturityActionRequest,
    x_workspace_id: str = Header(...),
) -> MaturityGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except MaturityGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
