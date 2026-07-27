from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_capability_registry import (
    CapabilityMatchRequest,
    CapabilityMatchResult,
    CapabilityRegistryAction,
    CapabilityRegistryCreate,
    CapabilityRegistryRecord,
)
from app.services.agent_capability_registry import agent_capability_registry_service

router = APIRouter(prefix="/v1/agent-capabilities", tags=["agent-capabilities"])


@router.get("/status")
def status() -> dict:
    return agent_capability_registry_service.status()


@router.post("/records", response_model=CapabilityRegistryRecord)
def create_record(payload: CapabilityRegistryCreate) -> CapabilityRegistryRecord:
    try:
        return agent_capability_registry_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[CapabilityRegistryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[CapabilityRegistryRecord]:
    return agent_capability_registry_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=CapabilityRegistryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> CapabilityRegistryRecord:
    try:
        return agent_capability_registry_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=CapabilityRegistryRecord)
def act(record_id: str, payload: CapabilityRegistryAction) -> CapabilityRegistryRecord:
    try:
        return agent_capability_registry_service.act(
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


@router.post("/match", response_model=list[CapabilityMatchResult])
def match_agents(payload: CapabilityMatchRequest) -> list[CapabilityMatchResult]:
    return agent_capability_registry_service.match(payload)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return agent_capability_registry_service.audit(workspace_id)
