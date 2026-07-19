from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveMarketPortfolio, MarketListResponse, MarketPortfolioCreate, MarketStatusResponse, SignalUpdate
from .service import executive_market_service

router = APIRouter(tags=["executive-market"])


@router.get("/v1/executive-market/status", response_model=MarketStatusResponse)
def market_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MarketStatusResponse:
    return executive_market_service.status(workspace_id)


@router.post("/v1/executive-market/portfolios", response_model=ExecutiveMarketPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: MarketPortfolioCreate) -> ExecutiveMarketPortfolio:
    try:
        return executive_market_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-market/portfolios", response_model=MarketListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> MarketListResponse:
    items = executive_market_service.list_portfolios(workspace_id)
    return MarketListResponse(items=items, count=len(items))


@router.get("/v1/executive-market/portfolios/{portfolio_id}", response_model=ExecutiveMarketPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMarketPortfolio:
    item = executive_market_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive market portfolio not found")
    return item


@router.post("/v1/executive-market/portfolios/{portfolio_id}/signals", response_model=ExecutiveMarketPortfolio)
def update_signal(portfolio_id: UUID, payload: SignalUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMarketPortfolio:
    try:
        return executive_market_service.update_signal(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-market/portfolios/{portfolio_id}/assess", response_model=ExecutiveMarketPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMarketPortfolio:
    try:
        return executive_market_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-market/audit", response_model=list[AuditRecord])
def market_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_market_service.audit_records(workspace_id)
