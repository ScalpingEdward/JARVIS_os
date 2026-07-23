from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, LearningActionRequest, LearningCreate, OperationalLearningRecord
from .service import OperationalLearningError, service

router = APIRouter(prefix="/v1/operational-learning", tags=["PHOENIX v21.37 Operational Learning"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "operational-learning", "version": "21.37", "status": "ready"}


@router.post("/records", response_model=OperationalLearningRecord)
def create_record(payload: LearningCreate) -> OperationalLearningRecord:
    try:
        return service.create(payload)
    except OperationalLearningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OperationalLearningRecord])
def list_records(x_workspace_id: str = Header(...)) -> list[OperationalLearningRecord]:
    return service.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=OperationalLearningRecord)
def get_record(record_id: str, x_workspace_id: str = Header(...)) -> OperationalLearningRecord:
    try:
        return service.get(record_id, x_workspace_id)
    except OperationalLearningError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OperationalLearningRecord)
def act_on_record(
    record_id: str,
    request: LearningActionRequest,
    x_workspace_id: str = Header(...),
) -> OperationalLearningRecord:
    try:
        return service.act(record_id, x_workspace_id, request)
    except OperationalLearningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
