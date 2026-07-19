from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutiveReputationPortfolio, ReputationIssueUpdate, ReputationListResponse, ReputationPortfolioCreate, ReputationStatusResponse
from .service import executive_reputation_service

router = APIRouter(tags=["executive-reputation"])


@router.get("/v1/executive-reputation/status", response_model=ReputationStatusResponse)
def reputation_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ReputationStatusResponse:
    return executive_reputation_service.status(workspace_id)


@router.post("/v1/executive-reputation/portfolios", response_model=ExecutiveReputationPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: ReputationPortfolioCreate) -> ExecutiveReputationPortfolio:
    try:
        return executive_reputation_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-reputation/portfolios", response_model=ReputationListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> ReputationListResponse:
    items = executive_reputation_service.list_portfolios(workspace_id)
    return ReputationListResponse(items=items, count=len(items))


@router.get("/v1/executive-reputation/portfolios/{portfolio_id}", response_model=ExecutiveReputationPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveReputationPortfolio:
    item = executive_reputation_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive reputation portfolio not found")
    return item


@router.post("/v1/executive-reputation/portfolios/{portfolio_id}/issues", response_model=ExecutiveReputationPortfolio)
def update_issue(portfolio_id: UUID, payload: ReputationIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveReputationPortfolio:
    try:
        return executive_reputation_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-reputation/portfolios/{portfolio_id}/assess", response_model=ExecutiveReputationPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveReputationPortfolio:
    try:
        return executive_reputation_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-reputation/audit", response_model=list[AuditRecord])
def reputation_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_reputation_service.audit_records(workspace_id)
