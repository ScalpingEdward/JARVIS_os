from fastapi import APIRouter, HTTPException, Query

from app.schemas.change_release_governance import (
    ChangeReleaseAction,
    ChangeReleaseGovernanceCreate,
    ChangeReleaseGovernanceRecord,
)
from app.services.change_release_governance import change_release_governance_service


router = APIRouter(prefix="/v1/change-release-governance", tags=["change-release-governance"])


@router.get("/status")
def status() -> dict:
    return change_release_governance_service.status()


@router.post("/records", response_model=ChangeReleaseGovernanceRecord)
def create_record(payload: ChangeReleaseGovernanceCreate) -> ChangeReleaseGovernanceRecord:
    try:
        return change_release_governance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ChangeReleaseGovernanceRecord])
def list_records(workspace_id: str = Query(...)) -> list[ChangeReleaseGovernanceRecord]:
    return change_release_governance_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ChangeReleaseGovernanceRecord)
def get_record(record_id: str, workspace_id: str = Query(...)) -> ChangeReleaseGovernanceRecord:
    try:
        return change_release_governance_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ChangeReleaseGovernanceRecord)
def act_on_record(record_id: str, payload: ChangeReleaseAction) -> ChangeReleaseGovernanceRecord:
    try:
        return change_release_governance_service.act(
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
def audit(workspace_id: str = Query(...)) -> list[dict]:
    return [entry.__dict__ for entry in change_release_governance_service.audit(workspace_id)]
