from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.executive_champion_challenger.api import router as executive_champion_challenger_router
from app.executive_evidence_intelligence.api import router as executive_evidence_intelligence_router
from app.executive_market_regime.api import router as executive_market_regime_router
from app.executive_shadow_trading.api import router as executive_shadow_trading_router

from .models import (
    AuditRecord,
    ExecutiveOrderFlowPortfolio,
    OrderFlowListResponse,
    OrderFlowPortfolioCreate,
    OrderFlowRiskUpdate,
    OrderFlowStatusResponse,
)
from .service import executive_order_flow_service

router = APIRouter(tags=["executive-order-flow"])


@router.get("/v1/executive-order-flow/status", response_model=OrderFlowStatusResponse)
def order_flow_status(workspace_id: str = Query(min_length=1, max_length=100)) -> OrderFlowStatusResponse:
    return executive_order_flow_service.status(workspace_id)


@router.post("/v1/executive-order-flow/portfolios", response_model=ExecutiveOrderFlowPortfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: OrderFlowPortfolioCreate) -> ExecutiveOrderFlowPortfolio:
    try:
        return executive_order_flow_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-order-flow/portfolios", response_model=OrderFlowListResponse)
def list_portfolios(workspace_id: str = Query(min_length=1, max_length=100)) -> OrderFlowListResponse:
    items = executive_order_flow_service.list_portfolios(workspace_id)
    return OrderFlowListResponse(items=items, count=len(items))


@router.get("/v1/executive-order-flow/portfolios/{portfolio_id}", response_model=ExecutiveOrderFlowPortfolio)
def get_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveOrderFlowPortfolio:
    item = executive_order_flow_service.get(portfolio_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Executive order-flow portfolio not found")
    return item


@router.post("/v1/executive-order-flow/portfolios/{portfolio_id}/risks", response_model=ExecutiveOrderFlowPortfolio)
def update_risk(portfolio_id: UUID, payload: OrderFlowRiskUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveOrderFlowPortfolio:
    try:
        return executive_order_flow_service.update_risk(portfolio_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-order-flow/portfolios/{portfolio_id}/assess", response_model=ExecutiveOrderFlowPortfolio)
def assess_portfolio(portfolio_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveOrderFlowPortfolio:
    try:
        return executive_order_flow_service.assess(portfolio_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-order-flow/audit", response_model=list[AuditRecord])
def order_flow_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_order_flow_service.audit_records(workspace_id)


router.include_router(executive_shadow_trading_router)
router.include_router(executive_champion_challenger_router)
router.include_router(executive_market_regime_router)
router.include_router(executive_evidence_intelligence_router)
