from fastapi import APIRouter, HTTPException, Query

from app.schemas.evidence_reasoning_context import (
    ReasoningContextAction,
    ReasoningContextCreate,
    ReasoningContextPacket,
)
from app.services.evidence_reasoning_context import evidence_aware_reasoning_context_service as service

router = APIRouter(prefix="/v1/evidence-reasoning-context", tags=["evidence-reasoning-context"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=ReasoningContextPacket)
def create_record(payload: ReasoningContextCreate) -> ReasoningContextPacket:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ReasoningContextPacket])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ReasoningContextPacket]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ReasoningContextPacket)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ReasoningContextPacket:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ReasoningContextPacket)
def act(record_id: str, payload: ReasoningContextAction) -> ReasoningContextPacket:
    try:
        return service.act(record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return service.audit(workspace_id)
