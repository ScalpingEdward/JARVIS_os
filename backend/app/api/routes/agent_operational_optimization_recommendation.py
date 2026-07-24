from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_operational_optimization_recommendation import (
    OptimizationAction,
    OptimizationCreate,
    OptimizationRecord,
)
from app.services.agent_operational_optimization_recommendation import (
    agent_operational_optimization_recommendation_service as service,
)

router = APIRouter(prefix="/v1/agent-operational-optimization", tags=["agent-operational-optimization"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=OptimizationRecord)
def create_record(payload: OptimizationCreate) -> OptimizationRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OptimizationRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[OptimizationRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=OptimizationRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> OptimizationRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OptimizationRecord)
def act(record_id: str, payload: OptimizationAction) -> OptimizationRecord:
    try:
        return service.act(
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
    return service.audit(workspace_id)
