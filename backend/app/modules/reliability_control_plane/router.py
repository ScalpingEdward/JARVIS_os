from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, ReliabilityAction, ReliabilityCreate, ReliabilityRecord
from .service import ReliabilityControlPlaneError, service

router = APIRouter(prefix="/v1/reliability-control-plane", tags=["reliability-control-plane"])


def workspace(x_workspace_id: str = Header(...)) -> str:
    return x_workspace_id


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "PHOENIX v21.28", "status": "ready"}


@router.post("/assessments", response_model=ReliabilityRecord)
def create_assessment(payload: ReliabilityCreate) -> ReliabilityRecord:
    try:
        return service.create(payload)
    except ReliabilityControlPlaneError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessments", response_model=list[ReliabilityRecord])
def list_assessments(x_workspace_id: str = Header(...)) -> list[ReliabilityRecord]:
    return service.list(x_workspace_id)


@router.get("/assessments/{record_id}", response_model=ReliabilityRecord)
def get_assessment(record_id: str, x_workspace_id: str = Header(...)) -> ReliabilityRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except ReliabilityControlPlaneError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/assessments/{record_id}/actions", response_model=ReliabilityRecord)
def act(record_id: str, action: ReliabilityAction, x_workspace_id: str = Header(...)) -> ReliabilityRecord:
    try:
        return service.act(record_id, x_workspace_id, action)
    except ReliabilityControlPlaneError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
