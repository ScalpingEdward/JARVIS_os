from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, GovernanceActionRequest, GovernanceSynthesisCreate, GovernanceSynthesisRecord
from .service import GovernanceSynthesisError, service

router = APIRouter(prefix="/v1/governance-synthesis", tags=["PHOENIX v21.39 Governance Synthesis"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "governance-synthesis", "version": "21.39", "status": "ready"}


@router.post("/records", response_model=GovernanceSynthesisRecord)
def create_record(payload: GovernanceSynthesisCreate) -> GovernanceSynthesisRecord:
    try:
        return service.create(payload)
    except GovernanceSynthesisError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[GovernanceSynthesisRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[GovernanceSynthesisRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=GovernanceSynthesisRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> GovernanceSynthesisRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except GovernanceSynthesisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=GovernanceSynthesisRecord)
def act_on_record(record_id: str, request: GovernanceActionRequest, x_workspace_id: str = Header(...)) -> GovernanceSynthesisRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except GovernanceSynthesisError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
