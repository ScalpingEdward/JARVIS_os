from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.schemas.market_microstructure_liquidity import (
    MicrostructureAction,
    MicrostructureRecord,
    MicrostructureRecordCreate,
)
from app.services.market_microstructure_liquidity import market_microstructure_store

router = APIRouter(prefix="/v1/market-microstructure", tags=["market-microstructure"])


@router.get("/status")
def status_endpoint() -> dict[str, object]:
    return {
        "module": "PHOENIX v21.68",
        "status": "operational",
        "execution_enabled": False,
        "human_approval_required": True,
        "risk_brain_authoritative": True,
    }


@router.post("/records", response_model=MicrostructureRecord, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: MicrostructureRecordCreate,
    x_workspace_id: str = Header(alias="X-Workspace-ID"),
) -> MicrostructureRecord:
    if payload.workspace_id != x_workspace_id:
        raise HTTPException(status_code=403, detail="workspace mismatch")
    try:
        return market_microstructure_store.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[MicrostructureRecord])
def list_records(x_workspace_id: str = Header(alias="X-Workspace-ID")) -> list[MicrostructureRecord]:
    return market_microstructure_store.list(x_workspace_id)


@router.get("/records/{record_id}", response_model=MicrostructureRecord)
def get_record(
    record_id: UUID,
    x_workspace_id: str = Header(alias="X-Workspace-ID"),
) -> MicrostructureRecord:
    try:
        return market_microstructure_store.get(record_id, x_workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=MicrostructureRecord)
def apply_action(
    record_id: UUID,
    payload: MicrostructureAction,
    x_workspace_id: str = Header(alias="X-Workspace-ID"),
) -> MicrostructureRecord:
    try:
        return market_microstructure_store.act(record_id, x_workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit_events(x_workspace_id: str = Header(alias="X-Workspace-ID")) -> list[dict]:
    return [event for event in market_microstructure_store.audit if event["workspace_id"] == x_workspace_id]
