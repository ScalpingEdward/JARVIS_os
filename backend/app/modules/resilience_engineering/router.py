from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ResilienceActionRequest, ResilienceCreate, ResilienceGovernanceRecord
from .service import ResilienceGovernanceError, service

router = APIRouter(prefix="/v1/resilience-engineering", tags=["PHOENIX v21.50 Resilience Engineering Continuity Testing"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "resilience-engineering-continuity-testing", "version": "21.50", "status": "ready"}


@router.post("/records", response_model=ResilienceGovernanceRecord)
def create_record(payload: ResilienceCreate) -> ResilienceGovernanceRecord:
    try:
        return service.create(payload)
    except ResilienceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ResilienceGovernanceRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[ResilienceGovernanceRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=ResilienceGovernanceRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> ResilienceGovernanceRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except ResilienceGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ResilienceGovernanceRecord)
def act_on_record(record_id: str, request: ResilienceActionRequest, x_workspace_id: str = Header(...)) -> ResilienceGovernanceRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except ResilienceGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
