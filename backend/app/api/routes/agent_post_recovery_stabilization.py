from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_post_recovery_stabilization import PostRecoveryAction, PostRecoveryCreate, PostRecoveryRecord
from app.services.agent_post_recovery_stabilization import agent_post_recovery_stabilization_service

router = APIRouter(prefix="/v1/agent-post-recovery", tags=["agent-post-recovery"])


@router.get("/status")
def status() -> dict:
    return agent_post_recovery_stabilization_service.status()


@router.post("/records", response_model=PostRecoveryRecord)
def create_record(payload: PostRecoveryCreate) -> PostRecoveryRecord:
    try:
        return agent_post_recovery_stabilization_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[PostRecoveryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[PostRecoveryRecord]:
    return agent_post_recovery_stabilization_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=PostRecoveryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> PostRecoveryRecord:
    try:
        return agent_post_recovery_stabilization_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=PostRecoveryRecord)
def act(record_id: str, payload: PostRecoveryAction) -> PostRecoveryRecord:
    try:
        return agent_post_recovery_stabilization_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id, payload.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_post_recovery_stabilization_service.audit(workspace_id)]
