from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_resilience_capacity_stress import CapacityStressAction, CapacityStressCreate, CapacityStressRecord
from app.services.agent_resilience_capacity_stress import agent_resilience_capacity_stress_service

router = APIRouter(prefix="/v1/agent-resilience-capacity", tags=["agent-resilience-capacity"])


@router.get("/status")
def status() -> dict:
    return agent_resilience_capacity_stress_service.status()


@router.post("/records", response_model=CapacityStressRecord)
def create_record(payload: CapacityStressCreate) -> CapacityStressRecord:
    try:
        return agent_resilience_capacity_stress_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CapacityStressRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[CapacityStressRecord]:
    return agent_resilience_capacity_stress_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=CapacityStressRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> CapacityStressRecord:
    try:
        return agent_resilience_capacity_stress_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CapacityStressRecord)
def act(record_id: str, payload: CapacityStressAction) -> CapacityStressRecord:
    try:
        return agent_resilience_capacity_stress_service.act(
            payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id, payload.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in agent_resilience_capacity_stress_service.audit(workspace_id)]
