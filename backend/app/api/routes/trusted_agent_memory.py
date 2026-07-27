from fastapi import APIRouter, HTTPException, Query

from app.schemas.trusted_agent_memory import (
    TrustedMemoryAction,
    TrustedMemoryCreate,
    TrustedMemoryHit,
    TrustedMemoryRecord,
    TrustedMemoryRetrieve,
)
from app.services.trusted_agent_memory import trusted_agent_memory_service as service

router = APIRouter(prefix="/v1/trusted-agent-memory", tags=["trusted-agent-memory"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=TrustedMemoryRecord)
def create_record(payload: TrustedMemoryCreate) -> TrustedMemoryRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[TrustedMemoryRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[TrustedMemoryRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=TrustedMemoryRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> TrustedMemoryRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=TrustedMemoryRecord)
def act(record_id: str, payload: TrustedMemoryAction) -> TrustedMemoryRecord:
    try:
        return service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/retrieve", response_model=list[TrustedMemoryHit])
def retrieve(payload: TrustedMemoryRetrieve) -> list[TrustedMemoryHit]:
    return service.retrieve(payload)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
