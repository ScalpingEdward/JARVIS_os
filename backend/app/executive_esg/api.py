from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, EsgIssueUpdate, EsgListResponse, EsgPortfolioCreate, EsgStatusResponse, ExecutiveEsgPortfolio
from .service import executive_esg_service

router = APIRouter(tags=["executive-esg"])


@router.get("/v1/executive-esg/status", response_model=EsgStatusResponse)
def esg_status(workspace_id: str = Query(min_length=1, max_length=100)) -> EsgStatusResponse:
    return executive_esg_service.status(workspace_id)


@router.post("/v1/executive-esg/portfolios", response_model=ExecutiveEsgPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: EsgPortfolioCreate) -> ExecutiveEsgPortfolio:
    try:
        return executive_esg_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-esg/portfolios", response_model=EsgListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> EsgListResponse:
    items = executive_esg_service.list_portfolios(workspace_id)
    return EsgListResponse(items=items, count=len(items))


@router.get("/v1/executive-esg/portfolios/{portfolio_id}", response_model=ExecutiveEsgPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEsgPortfolio:
    item = executive_esg_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive ESG portfolio not found")
    return item


@router.post("/v1/executive-esg/portfolios/{portfolio_id}/issues", response_model=ExecutiveEsgPortfolio)
def update_issue(portfolio_id: UUID, payload: EsgIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEsgPortfolio:
    try:
        return executive_esg_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-esg/portfolios/{portfolio_id}/assess", response_model=ExecutiveEsgPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveEsgPortfolio:
    try:
        return executive_esg_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-esg/audit", response_model=list[AuditRecord])
def esg_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_esg_service.audit_records(workspace_id)
