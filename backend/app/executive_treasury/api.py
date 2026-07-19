from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveTreasuryPortfolio, TreasuryListResponse, TreasuryPortfolioCreate, TreasuryRiskUpdate, TreasuryStatusResponse
from .service import executive_treasury_service

router = APIRouter(tags=["executive-treasury"])


@router.get("/v1/executive-treasury/status", response_model=TreasuryStatusResponse)
def treasury_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TreasuryStatusResponse:
    return executive_treasury_service.status(workspace_id)


@router.post("/v1/executive-treasury/portfolios", response_model=ExecutiveTreasuryPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: TreasuryPortfolioCreate) -> ExecutiveTreasuryPortfolio:
    try:
        return executive_treasury_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-treasury/portfolios", response_model=TreasuryListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> TreasuryListResponse:
    items = executive_treasury_service.list_portfolios(workspace_id)
    return TreasuryListResponse(items=items, count=len(items))


@router.get("/v1/executive-treasury/portfolios/{portfolio_id}", response_model=ExecutiveTreasuryPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTreasuryPortfolio:
    item = executive_treasury_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive treasury portfolio not found")
    return item


@router.post("/v1/executive-treasury/portfolios/{portfolio_id}/risks", response_model=ExecutiveTreasuryPortfolio)
def update_risk(portfolio_id: UUID, payload: TreasuryRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTreasuryPortfolio:
    try:
        return executive_treasury_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-treasury/portfolios/{portfolio_id}/assess", response_model=ExecutiveTreasuryPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTreasuryPortfolio:
    try:
        return executive_treasury_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-treasury/audit", response_model=list[AuditRecord])
def treasury_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_treasury_service.audit_records(workspace_id)


from app.executive_investor.api import router as executive_investor_router

router.include_router(executive_investor_router)
