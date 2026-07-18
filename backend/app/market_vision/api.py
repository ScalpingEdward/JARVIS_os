from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..agent_orchestrator.api import router as agent_orchestrator_router
from ..ai_connector_hub.api import router as ai_connector_hub_router
from ..asset_cmdb.api import router as asset_cmdb_router
from ..audit_compliance.api import router as audit_compliance_router
from ..automation_runtime.api import router as automation_runtime_router
from ..autonomous_research.api import router as autonomous_research_router
from ..backup_recovery.api import router as backup_recovery_router
from ..backtesting_lab.api import router as backtesting_lab_router
from ..browser_intelligence.api import router as browser_intelligence_router
from ..capital_allocation.api import router as capital_allocation_router
from ..change_governance.api import router as change_governance_router
from ..collaboration_mesh.api import router as collaboration_mesh_router
from ..command_center.api import router as command_center_router
from ..compliance_evidence.api import router as compliance_evidence_router
from ..config_control.api import router as config_control_router
from ..dashboard_governance.api import router as dashboard_governance_router
from ..data_governance.api import router as data_governance_router
from ..decision_memory.api import router as decision_memory_router
from ..desktop_intelligence.api import router as desktop_intelligence_router
from ..digital_twin.api import router as digital_twin_router
from ..document_intelligence.api import router as document_intelligence_router
from ..event_bus.api import router as event_bus_router
from ..execution_simulator.api import router as execution_simulator_router
from ..forward_validation.api import router as forward_validation_router
from ..health_intelligence.api import router as health_intelligence_router
from ..identity_access.api import router as identity_access_router
from ..incident_management.api import router as incident_management_router
from ..integration_hub.api import router as integration_hub_router
from ..job_orchestrator.api import router as job_orchestrator_router
from ..knowledge_engine.api import router as knowledge_engine_router
from ..live_integrations.api import router as live_integrations_router
from ..localization.api import router as localization_router
from ..market_replay.api import router as market_replay_router
from ..memory_engine.api import router as memory_engine_router
from ..mission_control.api import router as mission_control_router
from ..multi_broker.api import router as multi_broker_router
from ..notification_hub.api import router as notification_hub_router
from ..observability_control.api import router as observability_control_router
from ..on_call_engine.api import router as on_call_engine_router
from ..personal_ceo.api import router as personal_ceo_router
from ..planning_intelligence.api import router as planning_intelligence_router
from ..playbook_engine.api import router as playbook_engine_router
from ..plugin_sdk.api import router as plugin_sdk_router
from ..policy_approval.api import router as policy_approval_router
from ..portfolio_risk.api import router as portfolio_risk_router
from ..predictive_intelligence.api import router as predictive_intelligence_router
from ..proactive_operations.api import router as proactive_operations_router
from ..readiness_center.api import router as readiness_center_router
from ..replay_intelligence.api import router as replay_intelligence_router
from ..resilience_engine.api import router as resilience_engine_router
from ..risk_allocation.api import router as risk_allocation_router
from ..runbook_engine.api import router as runbook_engine_router
from ..secrets_vault.api import router as secrets_vault_router
from ..service_registry.api import router as service_registry_router
from ..slo_engine.api import router as slo_engine_router
from ..strategic_planning.api import router as strategic_planning_router
from ..strategy_builder.api import router as strategy_builder_router
from ..strategy_coach.api import router as strategy_coach_router
from ..task_engine.api import router as task_engine_router
from ..temporal_scheduler.api import router as temporal_scheduler_router
from ..trade_approval.api import router as trade_approval_router
from ..vision_intelligence.api import router as vision_intelligence_router
from ..workflow_designer.api import router as workflow_designer_router
from .models import MarketVisionCreate, MarketVisionListResponse, MarketVisionRecord, MarketVisionStatus
from .service import market_vision_service

router = APIRouter(tags=["market-vision"])


@router.get("/v1/market-vision/status", response_model=MarketVisionStatus)
def vision_status() -> MarketVisionStatus:
    return market_vision_service.status()


@router.post("/v1/market-vision/analyses", response_model=MarketVisionRecord, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: MarketVisionCreate) -> MarketVisionRecord:
    return market_vision_service.create(payload)


@router.get("/v1/market-vision/analyses", response_model=MarketVisionListResponse)
def list_analyses(symbol: str | None = Query(default=None, max_length=40)) -> MarketVisionListResponse:
    items = market_vision_service.list_all(symbol=symbol)
    return MarketVisionListResponse(items=items, count=len(items))


@router.get("/v1/market-vision/analyses/{analysis_id}", response_model=MarketVisionRecord)
def get_analysis(analysis_id: UUID) -> MarketVisionRecord:
    record = market_vision_service.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market vision analysis not found")
    return record


@router.get("/v1/market-vision/latest/{symbol}", response_model=MarketVisionRecord)
def latest_analysis(symbol: str) -> MarketVisionRecord:
    record = market_vision_service.latest(symbol)
    if record is None:
        raise HTTPException(status_code=404, detail="No market vision analysis found")
    return record


router.include_router(autonomous_research_router)
router.include_router(personal_ceo_router)
router.include_router(live_integrations_router)
router.include_router(collaboration_mesh_router)
router.include_router(proactive_operations_router)
router.include_router(notification_hub_router)
router.include_router(config_control_router)
router.include_router(readiness_center_router)
router.include_router(digital_twin_router)
router.include_router(decision_memory_router)
router.include_router(strategic_planning_router)
router.include_router(predictive_intelligence_router)
router.include_router(portfolio_risk_router)
router.include_router(capital_allocation_router)
router.include_router(multi_broker_router)
router.include_router(strategy_builder_router)
router.include_router(backtesting_lab_router)
router.include_router(execution_simulator_router)
router.include_router(market_replay_router)
router.include_router(replay_intelligence_router)
router.include_router(strategy_coach_router)
router.include_router(forward_validation_router)
router.include_router(risk_allocation_router)
router.include_router(trade_approval_router)
router.include_router(agent_orchestrator_router)
router.include_router(memory_engine_router)
router.include_router(workflow_designer_router)
router.include_router(plugin_sdk_router)
router.include_router(automation_runtime_router)
router.include_router(ai_connector_hub_router)
router.include_router(knowledge_engine_router)
router.include_router(browser_intelligence_router)
router.include_router(document_intelligence_router)
router.include_router(vision_intelligence_router)
router.include_router(desktop_intelligence_router)
router.include_router(task_engine_router)
router.include_router(integration_hub_router)
router.include_router(observability_control_router)
router.include_router(policy_approval_router)
router.include_router(identity_access_router)
router.include_router(secrets_vault_router)
router.include_router(localization_router)
router.include_router(data_governance_router)
router.include_router(compliance_evidence_router)
router.include_router(service_registry_router)
router.include_router(event_bus_router)
router.include_router(job_orchestrator_router)
router.include_router(temporal_scheduler_router)
router.include_router(resilience_engine_router)
router.include_router(slo_engine_router)
router.include_router(incident_management_router)
router.include_router(change_governance_router)
router.include_router(runbook_engine_router)
router.include_router(on_call_engine_router)
router.include_router(asset_cmdb_router)
router.include_router(backup_recovery_router)
router.include_router(health_intelligence_router)
router.include_router(audit_compliance_router)
router.include_router(command_center_router)
router.include_router(dashboard_governance_router)
router.include_router(playbook_engine_router)
router.include_router(mission_control_router)
router.include_router(planning_intelligence_router)
