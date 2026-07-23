from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.portfolio_performance_attribution import (
    AttributionAction,
    AttributionRecord,
    AttributionRecordCreate,
)
from app.services.portfolio_performance_attribution import portfolio_attribution_service

router = APIRouter(prefix="/v1/portfolio-attribution", tags=["portfolio-attribution"])


@router.get("/status")
def status() -> dict:
    return portfolio_attribution_service.status()


@router.post("/records", response_model=AttributionRecord)
def create_record(payload: AttributionRecordCreate) -> AttributionRecord:
    try:
        return portfolio_attribution_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AttributionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AttributionRecord]:
    return portfolio_attribution_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AttributionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AttributionRecord:
    try:
        return portfolio_attribution_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AttributionRecord)
def apply_action(
    record_id: str,
    payload: AttributionAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> AttributionRecord:
    try:
        return portfolio_attribution_service.act(record_id, workspace_id, payload, x_risk_brain_blocked)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return portfolio_attribution_service.audit(workspace_id)
