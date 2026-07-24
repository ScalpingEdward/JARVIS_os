from fastapi import APIRouter, HTTPException, Query

from app.schemas.data_governance_lineage import (
    DataGovernanceAction,
    DataGovernanceCreate,
    DataGovernanceRecord,
)
from app.services.data_governance_lineage import data_governance_lineage_service


router = APIRouter(prefix="/v1/data-governance-lineage", tags=["data-governance-lineage"])


@router.get("/status")
def status() -> dict:
    return data_governance_lineage_service.status()


@router.post("/records", response_model=DataGovernanceRecord)
def create_record(payload: DataGovernanceCreate) -> DataGovernanceRecord:
    try:
        return data_governance_lineage_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[DataGovernanceRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[DataGovernanceRecord]:
    return data_governance_lineage_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=DataGovernanceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> DataGovernanceRecord:
    try:
        return data_governance_lineage_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=DataGovernanceRecord)
def act_on_record(record_id: str, payload: DataGovernanceAction) -> DataGovernanceRecord:
    try:
        return data_governance_lineage_service.act(
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
    return [entry.__dict__ for entry in data_governance_lineage_service.audit(workspace_id)]
