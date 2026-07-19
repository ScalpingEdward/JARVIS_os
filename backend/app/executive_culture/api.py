from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.executive_procurement.api import router as executive_procurement_router
from .models import AuditRecord, CultureIssueUpdate, CultureListResponse, CulturePortfolioCreate, CultureStatusResponse, ExecutiveCulturePortfolio
from .service import executive_culture_service

router = APIRouter(tags=["executive-culture"])


@router.get("/v1/executive-culture/status", response_model=CultureStatusResponse)
def culture_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CultureStatusResponse:
    return executive_culture_service.status(workspace_id)


@router.post("/v1/executive-culture/portfolios", response_model=ExecutiveCulturePortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: CulturePortfolioCreate) -> ExecutiveCulturePortfolio:
    try:
        return executive_culture_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-culture/portfolios", response_model=CultureListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> CultureListResponse:
    items = executive_culture_service.list_portfolios(workspace_id)
    return CultureListResponse(items=items, count=len(items))


@router.get("/v1/executive-culture/portfolios/{portfolio_id}", response_model=ExecutiveCulturePortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCulturePortfolio:
    item = executive_culture_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive culture portfolio not found")
    return item


@router.post("/v1/executive-culture/portfolios/{portfolio_id}/issues", response_model=ExecutiveCulturePortfolio)
def update_issue(portfolio_id: UUID, payload: CultureIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCulturePortfolio:
    try:
        return executive_culture_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-culture/portfolios/{portfolio_id}/assess", response_model=ExecutiveCulturePortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCulturePortfolio:
    try:
        return executive_culture_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-culture/audit", response_model=list[AuditRecord])
def culture_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_culture_service.audit_records(workspace_id)


router.include_router(executive_procurement_router)
