from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveTalentPortfolio, TalentListResponse, TalentPortfolioCreate, TalentStatusResponse, TalentUpdate
from .service import executive_talent_service
from app.executive_market.api import router as executive_market_router

router = APIRouter(tags=["executive-talent"])


@router.get("/v1/executive-talent/status", response_model=TalentStatusResponse)
def talent_status(workspace_id: str = Query(min_length=1, max_length=100)) -> TalentStatusResponse:
    return executive_talent_service.status(workspace_id)


@router.post("/v1/executive-talent/portfolios", response_model=ExecutiveTalentPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: TalentPortfolioCreate) -> ExecutiveTalentPortfolio:
    try:
        return executive_talent_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-talent/portfolios", response_model=TalentListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> TalentListResponse:
    items = executive_talent_service.list_portfolios(workspace_id)
    return TalentListResponse(items=items, count=len(items))


@router.get("/v1/executive-talent/portfolios/{portfolio_id}", response_model=ExecutiveTalentPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTalentPortfolio:
    item = executive_talent_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive talent portfolio not found")
    return item


@router.post("/v1/executive-talent/portfolios/{portfolio_id}/updates", response_model=ExecutiveTalentPortfolio)
def update_portfolio(portfolio_id: UUID, payload: TalentUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTalentPortfolio:
    try:
        return executive_talent_service.update(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-talent/portfolios/{portfolio_id}/assess", response_model=ExecutiveTalentPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveTalentPortfolio:
    try:
        return executive_talent_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-talent/audit", response_model=list[AuditRecord])
def talent_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_talent_service.audit_records(workspace_id)


router.include_router(executive_market_router)
