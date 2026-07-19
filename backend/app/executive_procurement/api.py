from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.executive_reputation.api import router as executive_reputation_router
from .models import AuditRecord, ExecutiveProcurementPortfolio, ProcurementListResponse, ProcurementPortfolioCreate, ProcurementStatusResponse, ThirdPartyIssueUpdate
from .service import executive_procurement_service

router = APIRouter(tags=["executive-procurement"])


@router.get("/v1/executive-procurement/status", response_model=ProcurementStatusResponse)
def procurement_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ProcurementStatusResponse:
    return executive_procurement_service.status(workspace_id)


@router.post("/v1/executive-procurement/portfolios", response_model=ExecutiveProcurementPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: ProcurementPortfolioCreate) -> ExecutiveProcurementPortfolio:
    try:
        return executive_procurement_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-procurement/portfolios", response_model=ProcurementListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> ProcurementListResponse:
    items = executive_procurement_service.list_portfolios(workspace_id)
    return ProcurementListResponse(items=items, count=len(items))


@router.get("/v1/executive-procurement/portfolios/{portfolio_id}", response_model=ExecutiveProcurementPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProcurementPortfolio:
    item = executive_procurement_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive procurement portfolio not found")
    return item


@router.post("/v1/executive-procurement/portfolios/{portfolio_id}/issues", response_model=ExecutiveProcurementPortfolio)
def update_issue(portfolio_id: UUID, payload: ThirdPartyIssueUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProcurementPortfolio:
    try:
        return executive_procurement_service.update_issue(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-procurement/portfolios/{portfolio_id}/assess", response_model=ExecutiveProcurementPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveProcurementPortfolio:
    try:
        return executive_procurement_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-procurement/audit", response_model=list[AuditRecord])
def procurement_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_procurement_service.audit_records(workspace_id)


router.include_router(executive_reputation_router)
