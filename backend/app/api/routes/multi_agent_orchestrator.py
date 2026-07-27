from fastapi import APIRouter, HTTPException, Query

from app.schemas.multi_agent_orchestrator import OrchestrationAction, OrchestrationCreate, OrchestrationRecord
from app.services.multi_agent_orchestrator import multi_agent_orchestrator_service

router = APIRouter(prefix="/v1/multi-agent-orchestrator", tags=["multi-agent-orchestrator"])


@router.get("/status")
def status() -> dict:
    return multi_agent_orchestrator_service.status()


@router.post("/records", response_model=OrchestrationRecord)
def create_record(payload: OrchestrationCreate) -> OrchestrationRecord:
    try:
        return multi_agent_orchestrator_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OrchestrationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[OrchestrationRecord]:
    return multi_agent_orchestrator_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=OrchestrationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> OrchestrationRecord:
    try:
        return multi_agent_orchestrator_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OrchestrationRecord)
def act(record_id: str, payload: OrchestrationAction) -> OrchestrationRecord:
    try:
        return multi_agent_orchestrator_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor,
            payload.operation_id, payload.task_id, payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return multi_agent_orchestrator_service.audit(workspace_id)
