from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AllocationUpdate,
    AuditRecord,
    CapitalListResponse,
    CapitalPortfolioCreate,
    CapitalStatusResponse,
    ExecutiveCapitalPortfolio,
)
from .service import executive_capital_service
from app.executive_talent.api import router as executive_talent_router

router = APIRouter(tags=["executive-capital"])
router.include_router(executive_talent_router)


@router.get("/v1/executive-capital/status", response_model=CapitalStatusResponse)
def capital_status(workspace_id: str = Query(min_length=1, max_length=100)) -> CapitalStatusResponse:
    return executive_capital_service.status(workspace_id)


@router.post("/v1/executive-capital/portfolios", response_model=ExecutiveCapitalPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: CapitalPortfolioCreate) -> ExecutiveCapitalPortfolio:
    try:
        return executive_capital_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-capital/portfolios", response_model=CapitalListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> CapitalListResponse:
    items = executive_capital_service.list_portfolios(workspace_id)
    return CapitalListResponse(items=items, count=len(items))


@router.get("/v1/executive-capital/portfolios/{portfolio_id}", response_model=ExecutiveCapitalPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCapitalPortfolio:
    record = executive_capital_service.get(portfolio_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive capital portfolio not found")
    return record


@router.post("/v1/executive-capital/portfolios/{portfolio_id}/allocations", response_model=ExecutiveCapitalPortfolio)
def update_allocation(portfolio_id: UUID, payload: AllocationUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCapitalPortfolio:
    try:
        return executive_capital_service.update_allocation(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-capital/portfolios/{portfolio_id}/assess", response_model=ExecutiveCapitalPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveCapitalPortfolio:
    try:
        return executive_capital_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-capital/audit", response_model=list[AuditRecord])
def capital_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_capital_service.audit_records(workspace_id)
