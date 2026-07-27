from fastapi import APIRouter, HTTPException, Query

from app.schemas.decision_synthesis_uncertainty import (
    DecisionSynthesisAction,
    DecisionSynthesisCreate,
    DecisionSynthesisRecord,
)
from app.services.decision_synthesis_uncertainty import decision_synthesis_uncertainty_service as service

router = APIRouter(prefix="/v1/decision-synthesis", tags=["decision-synthesis"])


@router.get("/status")
def status() -> dict:
    return service.status()


@router.post("/records", response_model=DecisionSynthesisRecord)
def create_record(payload: DecisionSynthesisCreate) -> DecisionSynthesisRecord:
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DecisionSynthesisRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[DecisionSynthesisRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DecisionSynthesisRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> DecisionSynthesisRecord:
    try:
        return service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=DecisionSynthesisRecord)
def act(record_id: str, payload: DecisionSynthesisAction) -> DecisionSynthesisRecord:
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
