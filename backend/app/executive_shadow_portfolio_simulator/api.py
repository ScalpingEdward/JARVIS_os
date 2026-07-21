from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ShadowPortfolioAudit,
    ShadowPortfolioCreate,
    ShadowPortfolioExecuteRequest,
    ShadowPortfolioRecord,
    ShadowPortfolioStatus,
)
from .service import shadow_portfolio_simulator_service

router = APIRouter(tags=["executive-shadow-portfolio-simulator"])


@router.get("/v1/executive-shadow-portfolio/status", response_model=ShadowPortfolioStatus)
def shadow_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return shadow_portfolio_simulator_service.status(workspace_id)


@router.post("/v1/executive-shadow-portfolio/simulations", response_model=ShadowPortfolioRecord, status_code=status.HTTP_201_CREATED)
def create_shadow_simulation(payload: ShadowPortfolioCreate):
    try:
        return shadow_portfolio_simulator_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-shadow-portfolio/simulations", response_model=list[ShadowPortfolioRecord])
def list_shadow_simulations(workspace_id: str = Query(min_length=1, max_length=100)):
    return shadow_portfolio_simulator_service.list_records(workspace_id)


@router.get("/v1/executive-shadow-portfolio/simulations/{record_id}", response_model=ShadowPortfolioRecord)
def get_shadow_simulation(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = shadow_portfolio_simulator_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="shadow portfolio record not found")
    return record


@router.post("/v1/executive-shadow-portfolio/simulations/{record_id}/execute", response_model=ShadowPortfolioRecord)
def execute_shadow_simulation(record_id: UUID, request: ShadowPortfolioExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return shadow_portfolio_simulator_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-shadow-portfolio/audit", response_model=list[ShadowPortfolioAudit])
def shadow_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return shadow_portfolio_simulator_service.audit_records(workspace_id)
