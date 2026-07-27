from fastapi import APIRouter, HTTPException, Query

from app.schemas.change_proposal_safe_execution import (
    ChangeProposalAction,
    ChangeProposalCreate,
    ChangeProposalRecord,
)
from app.services.change_proposal_safe_execution import change_proposal_safe_execution_service

router = APIRouter(prefix="/v1/change-proposals", tags=["change-proposals"])


@router.get("/status")
def status() -> dict:
    return change_proposal_safe_execution_service.status()


@router.post("/records", response_model=ChangeProposalRecord)
def create_record(payload: ChangeProposalCreate) -> ChangeProposalRecord:
    try:
        return change_proposal_safe_execution_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ChangeProposalRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ChangeProposalRecord]:
    return change_proposal_safe_execution_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ChangeProposalRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ChangeProposalRecord:
    try:
        return change_proposal_safe_execution_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ChangeProposalRecord)
def act(record_id: str, payload: ChangeProposalAction) -> ChangeProposalRecord:
    try:
        return change_proposal_safe_execution_service.act(
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
    return change_proposal_safe_execution_service.audit(workspace_id)
