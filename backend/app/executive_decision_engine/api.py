from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..executive_capital_allocation_deployment.api import router as executive_capital_allocation_deployment_router
from ..executive_live_capital_broker_deployment.api import router as executive_live_capital_broker_deployment_router
from ..executive_live_portfolio_exposure.api import router as executive_live_portfolio_exposure_router
from ..executive_live_rebalancing_strategy_rotation.api import router as executive_live_rebalancing_strategy_rotation_router
from ..executive_live_strategy_performance_lifecycle.api import router as executive_live_strategy_performance_lifecycle_router
from ..executive_live_strategy_probation_canary_expansion.api import router as executive_live_strategy_probation_canary_expansion_router
from ..executive_live_strategy_production_scale_capacity.api import router as executive_live_strategy_production_scale_capacity_router
from ..executive_live_strategy_review_retirement_knowledge.api import router as executive_live_strategy_review_retirement_knowledge_router
from ..executive_live_strategy_succession_replacement.api import router as executive_live_strategy_succession_replacement_router
from ..executive_prop_payout_capital_formation.api import router as executive_prop_payout_capital_formation_router
from ..executive_strategy.api import router as executive_strategy_router
from ..executive_telegram_chart_vision_signal_intelligence.api import router as executive_telegram_chart_vision_signal_intelligence_router
from ..executive_telegram_media_ingestion.api import router as executive_telegram_media_ingestion_router
from ..executive_trading_incident_recovery.api import router as executive_trading_incident_recovery_router
from ..executive_trading_post_release_drift.api import router as executive_trading_post_release_drift_router
from ..executive_trading_promotion_scaling.api import router as executive_trading_promotion_scaling_router
from ..executive_trading_readiness.api import router as executive_trading_readiness_router
from ..executive_trading_release_reentry.api import router as executive_trading_release_reentry_router
from ..executive_treasury_wealth_governance.api import router as executive_treasury_wealth_governance_router
from ..executive_vision_provider_routing.api import router as executive_vision_provider_routing_router
from .models import (
    ApprovalRequest,
    AuditRecord,
    DecisionListResponse,
    DecisionStatusResponse,
    ExecutiveDecision,
    ExecutiveDecisionCreate,
)
from .service import executive_decision_service
from .trading_api import router as trading_decision_router

router = APIRouter(tags=["executive-decisions"])


@router.get("/v1/executive-decisions/status", response_model=DecisionStatusResponse)
def decision_status(workspace_id: str = Query(min_length=1, max_length=100)) -> DecisionStatusResponse:
    return executive_decision_service.status(workspace_id)


@router.post("/v1/executive-decisions", response_model=ExecutiveDecision, status_code=status.HTTP_201_CREATED)
def create_decision(payload: ExecutiveDecisionCreate) -> ExecutiveDecision:
    try:
        return executive_decision_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-decisions", response_model=DecisionListResponse)
def list_decisions(workspace_id: str = Query(min_length=1, max_length=100)) -> DecisionListResponse:
    items = executive_decision_service.list_decisions(workspace_id)
    return DecisionListResponse(items=items, count=len(items))


@router.get("/v1/executive-decisions/{decision_id}", response_model=ExecutiveDecision)
def get_decision(decision_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    record = executive_decision_service.get(decision_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive decision not found")
    return record


@router.post("/v1/executive-decisions/{decision_id}/evaluate", response_model=ExecutiveDecision)
def evaluate_decision(decision_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    try:
        return executive_decision_service.evaluate(decision_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/v1/executive-decisions/{decision_id}/approve", response_model=ExecutiveDecision)
def approve_decision(decision_id: UUID, request: ApprovalRequest, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveDecision:
    try:
        return executive_decision_service.approve(decision_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-decisions/audit", response_model=list[AuditRecord])
def decision_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_decision_service.audit_records(workspace_id)


router.include_router(trading_decision_router)
router.include_router(executive_trading_readiness_router)
router.include_router(executive_trading_incident_recovery_router)
router.include_router(executive_trading_release_reentry_router)
router.include_router(executive_trading_post_release_drift_router)
router.include_router(executive_trading_promotion_scaling_router)
router.include_router(executive_capital_allocation_deployment_router)
router.include_router(executive_prop_payout_capital_formation_router)
router.include_router(executive_treasury_wealth_governance_router)
router.include_router(executive_live_capital_broker_deployment_router)
router.include_router(executive_live_portfolio_exposure_router)
router.include_router(executive_live_rebalancing_strategy_rotation_router)
router.include_router(executive_live_strategy_performance_lifecycle_router)
router.include_router(executive_live_strategy_review_retirement_knowledge_router)
router.include_router(executive_live_strategy_succession_replacement_router)
router.include_router(executive_live_strategy_probation_canary_expansion_router)
router.include_router(executive_live_strategy_production_scale_capacity_router)
router.include_router(executive_telegram_chart_vision_signal_intelligence_router)
router.include_router(executive_telegram_media_ingestion_router)
router.include_router(executive_vision_provider_routing_router)
router.include_router(executive_strategy_router)
