from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveMAPortfolio, IntegrationRiskUpdate, MAListResponse, MAPortfolioCreate, MAStatusResponse
from .service import executive_ma_service

router = APIRouter(tags=["executive-ma"])


@router.get("/v1/executive-ma/status", response_model=MAStatusResponse)
def ma_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MAStatusResponse:
    return executive_ma_service.status(workspace_id)


@router.post("/v1/executive-ma/portfolios", response_model=ExecutiveMAPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: MAPortfolioCreate) -> ExecutiveMAPortfolio:
    try:
        return executive_ma_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-ma/portfolios", response_model=MAListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> MAListResponse:
    items = executive_ma_service.list_portfolios(workspace_id)
    return MAListResponse(items=items, count=len(items))


@router.get("/v1/executive-ma/portfolios/{portfolio_id}", response_model=ExecutiveMAPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMAPortfolio:
    item = executive_ma_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive M&A portfolio not found")
    return item


@router.post("/v1/executive-ma/portfolios/{portfolio_id}/risks", response_model=ExecutiveMAPortfolio)
def update_risk(portfolio_id: UUID, payload: IntegrationRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMAPortfolio:
    try:
        return executive_ma_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-ma/portfolios/{portfolio_id}/assess", response_model=ExecutiveMAPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveMAPortfolio:
    try:
        return executive_ma_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-ma/audit", response_model=list[AuditRecord])
def ma_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_ma_service.audit_records(workspace_id)
