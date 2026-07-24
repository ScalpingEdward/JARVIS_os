from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_disaster_recovery_service_continuity import (
    DisasterRecoveryAction,
    DisasterRecoveryCreate,
    DisasterRecoveryRecord,
)
from app.services.agent_disaster_recovery_service_continuity import (
    agent_disaster_recovery_service_continuity_service,
)

router = APIRouter(prefix="/v1/agent-disaster-recovery", tags=["agent-disaster-recovery"])


@router.get("/status")
def status() -> dict:
    return agent_disaster_recovery_service_continuity_service.status()


@router.post("/records", response_model=DisasterRecoveryRecord)
def create_record(payload: DisasterRecoveryCreate) -> DisasterRecoveryRecord:
    try:
        return agent_disaster_recovery_service_continuity_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DisasterRecoveryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[DisasterRecoveryRecord]:
    return agent_disaster_recovery_service_continuity_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DisasterRecoveryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> DisasterRecoveryRecord:
    try:
        return agent_disaster_recovery_service_continuity_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=DisasterRecoveryRecord)
def act(record_id: str, payload: DisasterRecoveryAction) -> DisasterRecoveryRecord:
    try:
        return agent_disaster_recovery_service_continuity_service.act(
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
    return [entry.__dict__ for entry in agent_disaster_recovery_service_continuity_service.audit(workspace_id)]
