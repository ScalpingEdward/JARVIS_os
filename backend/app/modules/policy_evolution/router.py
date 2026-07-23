from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, PolicyEvolutionActionRequest, PolicyEvolutionCreate, PolicyEvolutionRecord
from .service import PolicyEvolutionError, service

router = APIRouter(prefix="/v1/policy-evolution", tags=["PHOENIX v21.38 Policy Evolution"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "policy-evolution", "version": "21.38", "status": "ready"}


@router.post("/records", response_model=PolicyEvolutionRecord)
def create_record(payload: PolicyEvolutionCreate) -> PolicyEvolutionRecord:
    try:
        return service.create(payload)
    except PolicyEvolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[PolicyEvolutionRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[PolicyEvolutionRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=PolicyEvolutionRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> PolicyEvolutionRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except PolicyEvolutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=PolicyEvolutionRecord)
def act_on_record(record_id: str, request: PolicyEvolutionActionRequest, x_workspace_id: str = Header(...)) -> PolicyEvolutionRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except PolicyEvolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
