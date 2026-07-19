from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CapitalMarketsRiskUpdate,
    ExecutiveInvestorPortfolio,
    InvestorListResponse,
    InvestorPortfolioCreate,
    InvestorStatusResponse,
)
from .service import executive_investor_service

router = APIRouter(tags=["executive-investor"])


@router.get("/v1/executive-investor/status", response_model=InvestorStatusResponse)
def investor_status(workspace_id: str = Query(min_length=1, max_length=100)) -> InvestorStatusResponse:
    return executive_investor_service.status(workspace_id)


@router.post(
    "/v1/executive-investor/portfolios",
    response_model=ExecutiveInvestorPortfolio,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio(payload: InvestorPortfolioCreate) -> ExecutiveInvestorPortfolio:
    try:
        return executive_investor_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-investor/portfolios", response_model=InvestorListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> InvestorListResponse:
    items = executive_investor_service.list_portfolios(workspace_id)
    return InvestorListResponse(items=items, count=len(items))


@router.get("/v1/executive-investor/portfolios/{portfolio_id}", response_model=ExecutiveInvestorPortfolio)
def get_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveInvestorPortfolio:
    item = executive_investor_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive investor-relations portfolio not found")
    return item


@router.post(
    "/v1/executive-investor/portfolios/{portfolio_id}/risks",
    response_model=ExecutiveInvestorPortfolio,
)
def update_risk(
    portfolio_id: UUID,
    payload: CapitalMarketsRiskUpdate,
    workspace_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveInvestorPortfolio:
    try:
        return executive_investor_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/v1/executive-investor/portfolios/{portfolio_id}/assess",
    response_model=ExecutiveInvestorPortfolio,
)
def assess_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> ExecutiveInvestorPortfolio:
    try:
        return executive_investor_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-investor/audit", response_model=list[AuditRecord])
def investor_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_investor_service.audit_records(workspace_id)


from app.executive_digital_venture.api import router as executive_digital_venture_router

router.include_router(executive_digital_venture_router)
