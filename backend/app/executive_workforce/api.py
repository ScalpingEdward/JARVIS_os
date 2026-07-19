from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.executive_culture.api import router as executive_culture_router
from .models import (
    AuditRecord,
    ExecutiveWorkforcePortfolio,
    TalentRiskUpdate,
    WorkforceListResponse,
    WorkforcePortfolioCreate,
    WorkforceStatusResponse,
)
from .service import executive_workforce_service

router = APIRouter(tags=["executive-workforce"])


@router.get("/v1/executive-workforce/status", response_model=WorkforceStatusResponse)
def workforce_status(workspace_id: str = Query(min_length=1, max_length=100)) -> WorkforceStatusResponse:
    return executive_workforce_service.status(workspace_id)


@router.post("/v1/executive-workforce/portfolios", response_model=ExecutiveWorkforcePortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: WorkforcePortfolioCreate) -> ExecutiveWorkforcePortfolio:
    try:
        return executive_workforce_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-workforce/portfolios", response_model=WorkforceListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> WorkforceListResponse:
    items = executive_workforce_service.list_portfolios(workspace_id)
    return WorkforceListResponse(items=items, count=len(items))


@router.get("/v1/executive-workforce/portfolios/{portfolio_id}", response_model=ExecutiveWorkforcePortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveWorkforcePortfolio:
    item = executive_workforce_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive workforce portfolio not found")
    return item


@router.post("/v1/executive-workforce/portfolios/{portfolio_id}/risks", response_model=ExecutiveWorkforcePortfolio)
def update_risk(portfolio_id: UUID, payload: TalentRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveWorkforcePortfolio:
    try:
        return executive_workforce_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-workforce/portfolios/{portfolio_id}/assess", response_model=ExecutiveWorkforcePortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveWorkforcePortfolio:
    try:
        return executive_workforce_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-workforce/audit", response_model=list[AuditRecord])
def workforce_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_workforce_service.audit_records(workspace_id)


router.include_router(executive_culture_router)
