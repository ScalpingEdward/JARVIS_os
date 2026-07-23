from fastapi import APIRouter, Header, HTTPException

from app.schemas.autonomous_risk_committee import (
    RiskCommitteeAction,
    RiskCommitteeCreate,
    RiskCommitteeRecord,
)
from app.services.autonomous_risk_committee import service

router = APIRouter(prefix="/v1/autonomous-risk-committee", tags=["autonomous-risk-committee"])


def workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def get_status() -> dict:
    return service.status()


@router.post("/records", response_model=RiskCommitteeRecord)
def create_record(payload: RiskCommitteeCreate, x_workspace_id: str | None = Header(default=None)):
    if payload.workspace_id != workspace(x_workspace_id):
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[RiskCommitteeRecord])
def list_records(x_workspace_id: str | None = Header(default=None)):
    return service.list(workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=RiskCommitteeRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)):
    try:
        return service.get(workspace(x_workspace_id), record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=RiskCommitteeRecord)
def apply_action(record_id: str, payload: RiskCommitteeAction, x_workspace_id: str | None = Header(default=None)):
    try:
        return service.act(workspace(x_workspace_id), record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def get_audit(x_workspace_id: str | None = Header(default=None)):
    return service.audit(workspace(x_workspace_id))
