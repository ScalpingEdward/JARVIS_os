from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.portfolio_risk_stress import (
    PortfolioRiskAction,
    PortfolioRiskRecord,
    PortfolioRiskRecordCreate,
)
from app.services.portfolio_risk_stress import portfolio_risk_stress_service

router = APIRouter(prefix="/v1/portfolio-risk-stress", tags=["portfolio-risk-stress"])


@router.get("/status")
def status() -> dict:
    return portfolio_risk_stress_service.status()


@router.post("/records", response_model=PortfolioRiskRecord)
def create_record(payload: PortfolioRiskRecordCreate) -> PortfolioRiskRecord:
    try:
        return portfolio_risk_stress_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[PortfolioRiskRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[PortfolioRiskRecord]:
    return portfolio_risk_stress_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=PortfolioRiskRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> PortfolioRiskRecord:
    try:
        return portfolio_risk_stress_service.get(record_id, workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=PortfolioRiskRecord)
def apply_action(
    record_id: str,
    payload: PortfolioRiskAction,
    workspace_id: str = Query(min_length=1),
    x_risk_brain_blocked: bool = Header(default=False),
) -> PortfolioRiskRecord:
    try:
        return portfolio_risk_stress_service.act(record_id, workspace_id, payload, x_risk_brain_blocked)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return portfolio_risk_stress_service.audit(workspace_id)
