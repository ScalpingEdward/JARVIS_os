from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalRequest,
    AuditRecord,
    PortfolioAnalysisRecord,
    PortfolioAnalysisRequest,
    PortfolioCreate,
    PortfolioRecord,
    PortfolioStatus,
)
from .service import planning_portfolio_service

router = APIRouter(prefix="/portfolios", tags=["planning-portfolio"])


@router.get("/status", response_model=PortfolioStatus)
def portfolio_status(workspace_id: str = Query(min_length=1, max_length=120)) -> PortfolioStatus:
    return planning_portfolio_service.status(workspace_id)


@router.post("", response_model=PortfolioRecord, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: PortfolioCreate) -> PortfolioRecord:
    try:
        return planning_portfolio_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[PortfolioRecord])
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PortfolioRecord]:
    return planning_portfolio_service.list_portfolios(workspace_id)


@router.get("/{portfolio_id}", response_model=PortfolioRecord)
def get_portfolio(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> PortfolioRecord:
    record = planning_portfolio_service.get(workspace_id, portfolio_id)
    if record is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return record


@router.post("/{portfolio_id}/analyze", response_model=PortfolioAnalysisRecord)
def analyze_portfolio(portfolio_id: UUID, payload: PortfolioAnalysisRequest) -> PortfolioAnalysisRecord:
    try:
        return planning_portfolio_service.analyze(portfolio_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{portfolio_id}/latest-analysis", response_model=PortfolioAnalysisRecord)
def latest_analysis(
    portfolio_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> PortfolioAnalysisRecord:
    portfolio = planning_portfolio_service.get(workspace_id, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    record = planning_portfolio_service.latest_analysis(portfolio_id)
    if record is None:
        raise HTTPException(status_code=404, detail="portfolio analysis not found")
    return record


@router.post("/{portfolio_id}/approve", response_model=PortfolioRecord)
def approve_portfolio(portfolio_id: UUID, payload: ApprovalRequest) -> PortfolioRecord:
    try:
        return planning_portfolio_service.approve(portfolio_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit/records", response_model=list[AuditRecord])
def portfolio_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return planning_portfolio_service.audit(workspace_id)
