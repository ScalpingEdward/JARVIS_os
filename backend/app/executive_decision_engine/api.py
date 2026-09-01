from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..executive_account_risk.api import router as executive_account_risk_router
from ..executive_broker_connectivity.api import router as executive_broker_connectivity_router
from ..executive_capital_allocation_deployment.api import router as executive_capital_allocation_deployment_router
from ..executive_configuration_registry.api import router as executive_configuration_registry_router
from ..executive_controlled_reentry.api import router as executive_controlled_reentry_router
from ..executive_copy_execution_drift_repair.api import router as executive_copy_execution_drift_repair_router
from ..executive_emergency_risk_containment.api import router as executive_emergency_risk_containment_router
from ..executive_event_bus.api import router as executive_event_bus_router
from ..executive_executor_transport_runtime.api import router as executive_executor_transport_runtime_router
from ..executive_live_account_portfolio_state.api import router as executive_live_account_portfolio_state_router
from ..executive_live_adapter_activation.api import router as executive_live_adapter_activation_router
from ..executive_live_capital_broker_deployment.api import router as executive_live_capital_broker_deployment_router
from ..executive_live_portfolio_exposure.api import router as executive_live_portfolio_exposure_router
from ..executive_live_rebalancing_strategy_rotation.api import router as executive_live_rebalancing_strategy_rotation_router
from ..executive_live_strategy_performance_lifecycle.api import router as executive_live_strategy_performance_lifecycle_router
from ..executive_live_strategy_probation_canary_expansion.api import router as executive_live_strategy_probation_canary_expansion_router
from ..executive_live_strategy_production_scale_capacity.api import router as executive_live_strategy_production_scale_capacity_router
from ..executive_live_strategy_review_retirement_knowledge.api import router as executive_live_strategy_review_retirement_knowledge_router
from ..executive_live_strategy_succession_replacement.api import router as executive_live_strategy_succession_replacement_router
from ..executive_market_data.api import router as executive_market_data_router
from ..executive_module_executor_adapter.api import router as executive_module_executor_adapter_router
from ..executive_mt5_break_even_scale_out.api import router as executive_mt5_break_even_scale_out_router
from ..executive_mt5_end_to_end_runtime_validation.api import router as executive_mt5_end_to_end_runtime_validation_router
from ..executive_mt5_live_state_sync.api import router as executive_mt5_live_state_sync_router
from ..executive_mt5_native_adapter_runtime.api import router as executive_mt5_native_adapter_runtime_router
from ..executive_mt5_order_command_deal_ingestion.api import router as executive_mt5_order_command_deal_ingestion_router
from ..executive_mt5_pending_order_oco.api import router as executive_mt5_pending_order_oco_router
from ..executive_mt5_position_lifecycle.api import router as executive_mt5_position_lifecycle_router
from ..executive_mt5_position_stream_trailing_stop.api import router as executive_mt5_position_stream_trailing_stop_router
from ..executive_mt5_runtime_bridge.api import router as executive_mt5_runtime_bridge_router
from ..executive_mt5_strategy_runtime_orchestrator.api import router as executive_mt5_strategy_runtime_orchestrator_router
from ..executive_mt5_trading_session_news_filter.api import router as executive_mt5_trading_session_news_filter_router
from ..executive_multi_account_copy_governance.api import router as executive_multi_account_copy_governance_router
from ..executive_multi_account_portfolio_manager.api import router as executive_multi_account_portfolio_manager_router
from ..executive_observability.api import router as executive_observability_router
from ..executive_operational_continuity.api import router as executive_operational_continuity_router
from ..executive_order_execution.api import router as executive_order_execution_router
from ..executive_order_routing.api import router as executive_order_routing_router
from ..executive_persistent_event_store.api import router as executive_persistent_event_store_router
from ..executive_policy_engine.api import router as executive_policy_engine_router
from ..executive_portfolio_risk_brain.api import router as executive_portfolio_risk_brain_router
from ..executive_position_lifecycle.api import router as executive_position_lifecycle_router
from ..executive_prop_payout_capital_formation.api import router as executive_prop_payout_capital_formation_router
from ..executive_sql_outbox_runtime.api import router as executive_sql_outbox_runtime_router
from ..executive_strategy.api import router as executive_strategy_router
from ..executive_telegram_chart_vision_signal_intelligence.api import router as executive_telegram_chart_vision_signal_intelligence_router
from ..executive_telegram_collector.api import router as executive_telegram_collector_router
from ..executive_telegram_media_ingestion.api import router as executive_telegram_media_ingestion_router
from ..executive_telegram_sdk_client.api import router as executive_telegram_sdk_client_router
from ..executive_telegram_transport.api import router as executive_telegram_transport_router
from ..executive_telethon_client_bootstrap.api import router as executive_telethon_client_bootstrap_router
from ..executive_trading_incident_recovery.api import router as executive_trading_incident_recovery_router
from ..executive_trading_post_release_drift.api import router as executive_trading_post_release_drift_router
from ..executive_trading_promotion_scaling.api import router as executive_trading_promotion_scaling_router
from ..executive_trading_readiness.api import router as executive_trading_readiness_router
from ..executive_trading_release_reentry.api import router as executive_trading_release_reentry_router
from ..executive_transactional_outbox.api import router as executive_transactional_outbox_router
from ..executive_treasury_wealth_governance.api import router as executive_treasury_wealth_governance_router
from ..executive_vision_adapter_consensus.api import router as executive_vision_adapter_consensus_router
from ..executive_vision_adapter_execution.api import router as executive_vision_adapter_execution_router
from ..executive_vision_adapter_registry.api import router as executive_vision_adapter_registry_router
from ..executive_vision_provider_routing.api import router as executive_vision_provider_routing_router
from ..executive_workflow_executor_runtime.api import router as executive_workflow_executor_runtime_router
from ..executive_workflow_orchestrator.api import router as executive_workflow_orchestrator_router
from .models import ApprovalRequest, AuditRecord, DecisionListResponse, DecisionStatusResponse, ExecutiveDecision, ExecutiveDecisionCreate
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
router.include_router(executive_event_bus_router)
router.include_router(executive_persistent_event_store_router)
router.include_router(executive_transactional_outbox_router)
router.include_router(executive_sql_outbox_runtime_router)
router.include_router(executive_workflow_orchestrator_router)
router.include_router(executive_workflow_executor_runtime_router)
router.include_router(executive_module_executor_adapter_router)
router.include_router(executive_executor_transport_runtime_router)
router.include_router(executive_observability_router)
router.include_router(executive_policy_engine_router)
router.include_router(executive_configuration_registry_router)
router.include_router(executive_broker_connectivity_router)
router.include_router(executive_market_data_router)
router.include_router(executive_order_routing_router)
router.include_router(executive_order_execution_router)
router.include_router(executive_position_lifecycle_router)
router.include_router(executive_account_risk_router)
router.include_router(executive_emergency_risk_containment_router)
router.include_router(executive_controlled_reentry_router)
router.include_router(executive_multi_account_copy_governance_router)
router.include_router(executive_copy_execution_drift_repair_router)
router.include_router(executive_operational_continuity_router)
router.include_router(executive_live_adapter_activation_router)
router.include_router(executive_mt5_runtime_bridge_router)
router.include_router(executive_mt5_order_command_deal_ingestion_router)
router.include_router(executive_mt5_position_lifecycle_router)
router.include_router(executive_mt5_position_stream_trailing_stop_router)
router.include_router(executive_mt5_break_even_scale_out_router)
router.include_router(executive_mt5_pending_order_oco_router)
router.include_router(executive_mt5_trading_session_news_filter_router)
# executive_mt5_portfolio_correlation_exposure_router is registered directly
# in main.py; re-including it here duplicated every one of its routes.
router.include_router(executive_mt5_strategy_runtime_orchestrator_router)
router.include_router(executive_mt5_end_to_end_runtime_validation_router)
router.include_router(executive_mt5_native_adapter_runtime_router)
# executive_mt5_live_order_executor_router is registered directly in
# main.py; re-including it here duplicated every one of its routes.
router.include_router(executive_mt5_live_state_sync_router)
router.include_router(executive_live_account_portfolio_state_router)
router.include_router(executive_portfolio_risk_brain_router)
router.include_router(executive_multi_account_portfolio_manager_router)
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
router.include_router(executive_telegram_sdk_client_router)
router.include_router(executive_telethon_client_bootstrap_router)
router.include_router(executive_telegram_transport_router)
router.include_router(executive_telegram_collector_router)
router.include_router(executive_telegram_media_ingestion_router)
router.include_router(executive_vision_adapter_execution_router)
router.include_router(executive_vision_adapter_consensus_router)
router.include_router(executive_vision_adapter_registry_router)
router.include_router(executive_vision_provider_routing_router)
router.include_router(executive_strategy_router)
