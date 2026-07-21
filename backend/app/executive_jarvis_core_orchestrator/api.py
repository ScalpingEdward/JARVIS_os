from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import JarvisCoreAudit, JarvisCoreCreate, JarvisCoreExecuteRequest, JarvisCoreRecord, JarvisCoreStatus
from .service import jarvis_core_orchestrator_service

router = APIRouter(prefix="/v1/executive-jarvis-core", tags=["executive-jarvis-core"])


@router.get("/status", response_model=JarvisCoreStatus)
def status(workspace_id: str = Query(..., min_length=1)):
    return jarvis_core_orchestrator_service.status(workspace_id)


@router.post("/orchestrations", response_model=JarvisCoreRecord)
def create(payload: JarvisCoreCreate):
    try:
        return jarvis_core_orchestrator_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orchestrations", response_model=list[JarvisCoreRecord])
def list_records(workspace_id: str = Query(..., min_length=1)):
    return jarvis_core_orchestrator_service.list_records(workspace_id)


@router.get("/orchestrations/{record_id}", response_model=JarvisCoreRecord)
def get_record(record_id: UUID, workspace_id: str = Query(..., min_length=1)):
    record = jarvis_core_orchestrator_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="JARVIS core record not found")
    return record


@router.post("/orchestrations/{record_id}/execute", response_model=JarvisCoreRecord)
def execute(record_id: UUID, request: JarvisCoreExecuteRequest, workspace_id: str = Query(..., min_length=1)):
    try:
        return jarvis_core_orchestrator_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[JarvisCoreAudit])
def audit(workspace_id: str = Query(..., min_length=1)):
    return jarvis_core_orchestrator_service.audit_records(workspace_id)
