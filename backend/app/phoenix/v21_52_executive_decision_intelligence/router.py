from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ExecutiveActionRequest, ExecutiveDecisionCreate, ExecutiveDecisionRecord
from .service import ExecutiveGovernanceError, service

router = APIRouter(
    prefix="/v1/executive-decision-intelligence",
    tags=["PHOENIX v21.52 Executive Decision Intelligence Strategic Governance"],
)


@router.get("/status")
def status() -> dict[str, str]:
    return {
        "module": "executive-decision-intelligence-strategic-governance",
        "version": "21.52",
        "status": "ready",
    }


@router.post("/records", response_model=ExecutiveDecisionRecord)
def create_record(payload: ExecutiveDecisionCreate) -> ExecutiveDecisionRecord:
    try:
        return service.create(payload)
    except ExecutiveGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ExecutiveDecisionRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[ExecutiveDecisionRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=ExecutiveDecisionRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> ExecutiveDecisionRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except ExecutiveGovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ExecutiveDecisionRecord)
def act_on_record(
    record_id: str,
    request: ExecutiveActionRequest,
    x_workspace_id: str = Header(...),
) -> ExecutiveDecisionRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except ExecutiveGovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
