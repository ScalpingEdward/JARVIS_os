from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    DigitalVentureListResponse,
    DigitalVenturePortfolioCreate,
    DigitalVentureStatusResponse,
    ExecutiveDigitalVenturePortfolio,
    VentureRiskUpdate,
)
from .service import executive_digital_venture_service

router = APIRouter(tags=["executive-digital-venture"])


@router.get("/v1/executive-digital-venture/status", response_model=DigitalVentureStatusResponse)
def digital_venture_status(workspace_id: str = Query(min_length=1, max_length=100)) -> DigitalVentureStatusResponse:
    return executive_digital_venture_service.status(workspace_id)


@router.post("/v1/executive-digital-venture/portfolios", response_model=ExecutiveDigitalVenturePortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: DigitalVenturePortfolioCreate) -> ExecutiveDigitalVenturePortfolio:
    try:
        return executive_digital_venture_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-digital-venture/portfolios", response_model=DigitalVentureListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> DigitalVentureListResponse:
    items = executive_digital_venture_service.list_portfolios(workspace_id)
    return DigitalVentureListResponse(items=items, count=len(items))


@router.get("/v1/executive-digital-venture/portfolios/{portfolio_id}", response_model=ExecutiveDigitalVenturePortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDigitalVenturePortfolio:
    item = executive_digital_venture_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive digital venture portfolio not found")
    return item


@router.post("/v1/executive-digital-venture/portfolios/{portfolio_id}/risks", response_model=ExecutiveDigitalVenturePortfolio)
def update_risk(portfolio_id: UUID, payload: VentureRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDigitalVenturePortfolio:
    try:
        return executive_digital_venture_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-digital-venture/portfolios/{portfolio_id}/assess", response_model=ExecutiveDigitalVenturePortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDigitalVenturePortfolio:
    try:
        return executive_digital_venture_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-digital-venture/audit", response_model=list[AuditRecord])
def digital_venture_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_digital_venture_service.audit_records(workspace_id)
