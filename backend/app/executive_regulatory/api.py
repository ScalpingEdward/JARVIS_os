from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.executive_workforce.api import router as executive_workforce_router
from .models import AuditRecord, ComplianceIssueUpdate, ExecutiveRegulatoryPortfolio, RegulatoryListResponse, RegulatoryPortfolioCreate, RegulatoryStatusResponse
from .service import executive_regulatory_service

router = APIRouter(tags=["executive-regulatory"])

@router.get("/v1/executive-regulatory/status", response_model=RegulatoryStatusResponse)
def regulatory_status(workspace_id: str = Query(min_length=1, max_length=100)) -> RegulatoryStatusResponse:
    return executive_regulatory_service.status(workspace_id)

@router.post("/v1/executive-regulatory/portfolios", response_model=ExecutiveRegulatoryPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: RegulatoryPortfolioCreate) -> ExecutiveRegulatoryPortfolio:
    try:
        return executive_regulatory_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/v1/executive-regulatory/portfolios", response_model=RegulatoryListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> RegulatoryListResponse:
    items = executive_regulatory_service.list_portfolios(workspace_id)
    return RegulatoryListResponse(items=items, count=len(items))

@router.get("/v1/executive-regulatory/portfolios/{portfolio_id}", response_model=ExecutiveRegulatoryPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRegulatoryPortfolio:
    item = executive_regulatory_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive regulatory portfolio not found")
    return item

@router.post("/v1/executive-regulatory/portfolios/{portfolio_id}/issues", response_model=ExecutiveRegulatoryPortfolio)
def update_issue(portfolio_id: UUID, payload: ComplianceIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRegulatoryPortfolio:
    try:
        return executive_regulatory_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/v1/executive-regulatory/portfolios/{portfolio_id}/assess", response_model=ExecutiveRegulatoryPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveRegulatoryPortfolio:
    try:
        return executive_regulatory_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/v1/executive-regulatory/audit", response_model=list[AuditRecord])
def regulatory_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_regulatory_service.audit_records(workspace_id)


router.include_router(executive_workforce_router)
