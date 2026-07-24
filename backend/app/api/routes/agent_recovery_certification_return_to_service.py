from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_recovery_certification_return_to_service import (
    RecoveryCertificationAction,
    RecoveryCertificationCreate,
    RecoveryCertificationRecord,
)
from app.services.agent_recovery_certification_return_to_service import (
    agent_recovery_certification_return_to_service_service,
)

router = APIRouter(prefix="/v1/agent-recovery-certification", tags=["agent-recovery-certification"])


@router.get("/status")
def status() -> dict:
    return agent_recovery_certification_return_to_service_service.status()


@router.post("/records", response_model=RecoveryCertificationRecord)
def create_record(payload: RecoveryCertificationCreate) -> RecoveryCertificationRecord:
    try:
        return agent_recovery_certification_return_to_service_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[RecoveryCertificationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[RecoveryCertificationRecord]:
    return agent_recovery_certification_return_to_service_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=RecoveryCertificationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> RecoveryCertificationRecord:
    try:
        return agent_recovery_certification_return_to_service_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=RecoveryCertificationRecord)
def act(record_id: str, payload: RecoveryCertificationAction) -> RecoveryCertificationRecord:
    try:
        return agent_recovery_certification_return_to_service_service.act(
            payload.workspace_id,
            record_id,
            payload.action,
            payload.actor,
            payload.operation_id,
            payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_recovery_certification_return_to_service_service.audit(workspace_id)]
