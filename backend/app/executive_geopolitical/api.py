from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ExecutiveGeopoliticalPortfolio,
    GeopoliticalEventUpdate,
    GeopoliticalListResponse,
    GeopoliticalPortfolioCreate,
    GeopoliticalStatusResponse,
)
from .service import executive_geopolitical_service

router = APIRouter(tags=["executive-geopolitical"])


@router.get("/v1/executive-geopolitical/status", response_model=GeopoliticalStatusResponse)
def geopolitical_status(workspace_id: str = Query(min_length=1, max_length=100)) -> GeopoliticalStatusResponse:
    return executive_geopolitical_service.status(workspace_id)


@router.post(
    "/v1/executive-geopolitical/portfolios",
    response_model=ExecutiveGeopoliticalPortfolio,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio(payload: GeopoliticalPortfolioCreate) -> ExecutiveGeopoliticalPortfolio:
    try:
        return executive_geopolitical_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-geopolitical/portfolios", response_model=GeopoliticalListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> GeopoliticalListResponse:
    items = executive_geopolitical_service.list_portfolios(workspace_id)
    return GeopoliticalListResponse(items=items, count=len(items))


@router.get("/v1/executive-geopolitical/portfolios/{portfolio_id}", response_model=ExecutiveGeopoliticalPortfolio)
def get_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveGeopoliticalPortfolio:
    item = executive_geopolitical_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive geopolitical portfolio not found")
    return item


@router.post(
    "/v1/executive-geopolitical/portfolios/{portfolio_id}/events",
    response_model=ExecutiveGeopoliticalPortfolio,
)
def update_event(
    portfolio_id: UUID,
    payload: GeopoliticalEventUpdate,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveGeopoliticalPortfolio:
    try:
        return executive_geopolitical_service.update_event(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/v1/executive-geopolitical/portfolios/{portfolio_id}/assess",
    response_model=ExecutiveGeopoliticalPortfolio,
)
def assess_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveGeopoliticalPortfolio:
    try:
        return executive_geopolitical_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-geopolitical/audit", response_model=list[AuditRecord])
def geopolitical_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_geopolitical_service.audit_records(workspace_id)


from app.executive_ma.api import router as executive_ma_router

router.include_router(executive_ma_router)
