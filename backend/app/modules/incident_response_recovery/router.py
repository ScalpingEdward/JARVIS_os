from fastapi import APIRouter, Header, HTTPException

from .models import IncidentAction, IncidentCreate, IncidentRecord
from .service import IncidentResponseError, service

router = APIRouter(prefix="/v1/incident-response-recovery", tags=["incident-response-recovery"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")
    return x_workspace_id


@router.get("/status")
def status():
    return {"module": "PHOENIX v21.26", "status": "ready", "autonomous_actions": False}


@router.post("/incidents", response_model=IncidentRecord)
def create_incident(payload: IncidentCreate):
    try:
        return service.create(payload)
    except (IncidentResponseError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/incidents", response_model=list[IncidentRecord])
def list_incidents(x_workspace_id: str | None = Header(default=None)):
    return service.list(_workspace(x_workspace_id))


@router.get("/incidents/{record_id}", response_model=IncidentRecord)
def get_incident(record_id: str, x_workspace_id: str | None = Header(default=None)):
    try:
        return service.get(record_id, _workspace(x_workspace_id))
    except IncidentResponseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/incidents/{record_id}/actions", response_model=IncidentRecord)
def act_on_incident(record_id: str, action: IncidentAction, x_workspace_id: str | None = Header(default=None)):
    try:
        return service.act(record_id, _workspace(x_workspace_id), action)
    except IncidentResponseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)):
    return service.audit(_workspace(x_workspace_id))
