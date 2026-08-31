from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response, status

from .account_state_sync.api import router as account_state_sync_router
from .accounts.api import router as accounts_router
from .agent_adapters.api import router as agent_adapters_router
from .strategies.api import router as strategies_router
from .strategy_orchestrator.api import router as strategy_orchestrator_router
from .api.routes.auron_demo1_approval_handoff_v21_260 import router as auron_demo1_approval_handoff_v21_260_router
from .api.routes.auron_demo1_approval_resolution_v21_261 import router as auron_demo1_approval_resolution_v21_261_router
from .api.routes.auron_demo1_approved_resume_gate_v21_262 import router as auron_demo1_approved_resume_gate_v21_262_router
from .api.routes.auron_demo1_execution_dispatch_gate_v21_263 import router as auron_demo1_execution_dispatch_gate_v21_263_router
from .api.routes.auron_demo1_execution_adapter_selection_v21_264 import router as auron_demo1_execution_adapter_selection_v21_264_router
from .api.routes.auron_demo1_adapter_preflight_readiness_v21_265 import router as auron_demo1_adapter_preflight_readiness_v21_265_router
from .api.routes.auron_demo1_controlled_adapter_invocation_v21_266 import router as auron_demo1_controlled_adapter_invocation_v21_266_router
from .api.routes.auron_demo1_adapter_dry_run_simulation_v21_267 import router as auron_demo1_adapter_dry_run_simulation_v21_267_router
from .api.routes.auron_demo1_execution_preview_review_v21_268 import router as auron_demo1_execution_preview_review_v21_268_router
from .api.routes.auron_demo1_conversational_core_v21_242 import router as auron_demo1_conversational_core_v21_242_router
from .api.routes.auron_demo1_conversation_memory_v21_243 import router as auron_demo1_conversation_memory_v21_243_router
from .api.routes.auron_demo1_execution_admission_gate_v21_257 import router as auron_demo1_execution_admission_gate_v21_257_router
from .api.routes.auron_demo1_execution_policy_controller_v21_258 import router as auron_demo1_execution_policy_controller_v21_258_router
from .api.routes.auron_demo1_policy_decision_ledger_v21_259 import router as auron_demo1_policy_decision_ledger_v21_259_router
from .api.routes.auron_demo1_retry_recovery_v21_255 import router as auron_demo1_retry_recovery_v21_255_router
from .api.routes.phoenix_demo1_approval_inbox_v21_228 import router as phoenix_demo1_approval_inbox_router
from .api.routes.phoenix_demo1_execution_orchestrator_v21_237 import router as phoenix_demo1_execution_orchestrator_router
from .api.routes.phoenix_demo1_integration_validation_v21_232 import router as phoenix_demo1_integration_validation_router
from .api.routes.phoenix_demo1_intent_router_v21_238 import router as phoenix_demo1_intent_router_v21_238
from .api.routes.phoenix_demo1_launch_console_v21_236 import router as phoenix_demo1_launch_console_router
from .api.routes.phoenix_demo1_memory_binding_v21_229 import router as phoenix_demo1_memory_binding_router
from .api.routes.phoenix_demo1_operator_acceptance_v21_233 import router as phoenix_demo1_operator_acceptance_router
from .api.routes.phoenix_demo1_operator_dashboard_v21_230 import router as phoenix_demo1_operator_dashboard_router
from .api.routes.phoenix_demo1_packaging_readiness_v21_234 import router as phoenix_demo1_packaging_readiness_router
from .api.routes.phoenix_demo1_release_candidate_v21_235 import router as phoenix_demo1_release_candidate_router
from .api.routes.phoenix_demo1_runtime_readiness_v21_226 import router as phoenix_demo1_runtime_readiness_router
from .api.routes.phoenix_demo1_tool_adapters_v21_231 import router as phoenix_demo1_tool_adapters_router
from .api.routes.phoenix_demo1_v21_225 import router as phoenix_demo1_router
from .api.routes.phoenix_demo1_voice_adapter_v21_227 import router as phoenix_demo1_voice_adapter_router
from .api.routes.phoenix_demo1_visual_core_v21_241 import router as phoenix_demo1_visual_core_v21_241_router
from .api.routes.phoenix_demo1_web_console_v21_239 import router as phoenix_demo1_web_console_router
from .api.routes.phoenix_demo1_web_console_v21_240 import router as phoenix_demo1_web_console_v21_240_router
from .approvals.api import router as approvals_router
from .autofix.api import router as autofix_router
from .collaboration.api import router as collaboration_router
from .commands.api import router as commands_router
from .company.api import router as company_router
from .company_runtime.api import router as company_runtime_router
from .config import get_settings
from .connector_runtime.api import router as connector_runtime_router
from .connector_setup.api import router as connector_setup_router
from .connectors.api import router as connectors_router
from .decision_engine.api import router as decision_engine_router
from .execution.api import router as execution_router
from .executive_mt5_portfolio_correlation_exposure.api import router as executive_mt5_portfolio_correlation_exposure_router
from .github_remote.api import router as github_remote_router
from .goal_execution.api import router as goal_execution_router
from .knowledge_graph.api import router as knowledge_graph_router
from .live_analysis.api import router as live_analysis_router
from .long_term_memory.api import router as long_term_memory_router
from .market_intelligence.api import router as market_intelligence_router
from .market_vision.api import router as market_vision_router
from .memory.models import MemoryCreate, MemoryListResponse, MemoryRecord
from .memory.service import memory_service
from .mobile.api import router as mobile_router
from .research.provider_api import router as research_provider_router
from .models.api import GenerateRequest, GenerateResponse, ProvidersResponse
from .models.contracts import ModelRequest
from .models.router import UnknownProviderError, model_router
from .mt5_bridge.api import router as mt5_bridge_router
from .orderflow.api import router as orderflow_router
from .orchestrator.models import (
    AgentCreate,
    AgentListResponse,
    AgentRecord,
    OrchestratorStatus,
    TaskCreate,
    TaskListResponse,
    TaskRecord,
    TaskStatus,
    TaskStatusUpdate,
)
from .orchestrator.service import orchestrator_service
from .planner.api import router as planner_router
from .radar.api import router as radar_router
from .roadmap.api import router as roadmap_router
from .runtime.api import router as runtime_router
from .sandbox.api import router as sandbox_router
from .self_reflection.api import router as self_reflection_router
from .simulation_engine.api import router as simulation_engine_router
from .strategic_planner.api import router as strategic_planner_router
from .tools.api import router as tools_router
from .trade_analyst.api import router as trade_analyst_router
from .trading.api import router as trading_router
from .tradingview_sync.api import router as tradingview_sync_router
from .vision.api import router as vision_router
from .voice.api import router as voice_router
from .workers.api import router as workers_router
from .world_model.api import router as world_model_router
from .workspace.api import router as workspace_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(account_state_sync_router)
app.include_router(accounts_router)
app.include_router(agent_adapters_router)
app.include_router(strategies_router)
app.include_router(strategy_orchestrator_router)
app.include_router(phoenix_demo1_router)
app.include_router(phoenix_demo1_runtime_readiness_router)
app.include_router(phoenix_demo1_voice_adapter_router)
app.include_router(phoenix_demo1_approval_inbox_router)
app.include_router(phoenix_demo1_memory_binding_router)
app.include_router(phoenix_demo1_operator_dashboard_router)
app.include_router(phoenix_demo1_tool_adapters_router)
app.include_router(phoenix_demo1_integration_validation_router)
app.include_router(phoenix_demo1_operator_acceptance_router)
app.include_router(phoenix_demo1_packaging_readiness_router)
app.include_router(phoenix_demo1_release_candidate_router)
app.include_router(phoenix_demo1_launch_console_router)
app.include_router(phoenix_demo1_execution_orchestrator_router)
app.include_router(phoenix_demo1_intent_router_v21_238)
app.include_router(phoenix_demo1_web_console_router)
app.include_router(phoenix_demo1_web_console_v21_240_router)
app.include_router(phoenix_demo1_visual_core_v21_241_router)
app.include_router(auron_demo1_conversational_core_v21_242_router)
app.include_router(auron_demo1_conversation_memory_v21_243_router)
app.include_router(auron_demo1_retry_recovery_v21_255_router)
app.include_router(auron_demo1_execution_admission_gate_v21_257_router)
app.include_router(auron_demo1_execution_policy_controller_v21_258_router)
app.include_router(auron_demo1_policy_decision_ledger_v21_259_router)
app.include_router(auron_demo1_approval_handoff_v21_260_router)
app.include_router(auron_demo1_approval_resolution_v21_261_router)
app.include_router(auron_demo1_approved_resume_gate_v21_262_router)
app.include_router(auron_demo1_execution_dispatch_gate_v21_263_router)
app.include_router(auron_demo1_execution_adapter_selection_v21_264_router)
app.include_router(auron_demo1_adapter_preflight_readiness_v21_265_router)
app.include_router(auron_demo1_controlled_adapter_invocation_v21_266_router)
app.include_router(auron_demo1_adapter_dry_run_simulation_v21_267_router)
app.include_router(auron_demo1_execution_preview_review_v21_268_router)
app.include_router(approvals_router)
app.include_router(autofix_router)
app.include_router(collaboration_router)
app.include_router(commands_router)
app.include_router(company_router)
app.include_router(company_runtime_router)
app.include_router(connector_runtime_router)
app.include_router(connector_setup_router)
app.include_router(connectors_router)
app.include_router(decision_engine_router)
app.include_router(execution_router)
app.include_router(executive_mt5_portfolio_correlation_exposure_router)
app.include_router(github_remote_router)
app.include_router(goal_execution_router)
app.include_router(knowledge_graph_router)
app.include_router(live_analysis_router)
app.include_router(long_term_memory_router)
app.include_router(market_intelligence_router)
app.include_router(market_vision_router)
app.include_router(mobile_router)
app.include_router(research_provider_router)
app.include_router(mt5_bridge_router)
app.include_router(orderflow_router)
app.include_router(planner_router)
app.include_router(radar_router)
app.include_router(roadmap_router)
app.include_router(runtime_router)
app.include_router(sandbox_router)
app.include_router(self_reflection_router)
app.include_router(simulation_engine_router)
app.include_router(strategic_planner_router)
app.include_router(tools_router)
app.include_router(trade_analyst_router)
app.include_router(trading_router)
app.include_router(tradingview_sync_router)
app.include_router(vision_router)
app.include_router(voice_router)
app.include_router(workers_router)
app.include_router(world_model_router)
app.include_router(workspace_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.version, "status": "online"}


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "healthy", "environment": settings.environment}


@app.get("/v1/models/providers", response_model=ProvidersResponse, tags=["models"])
def list_model_providers() -> ProvidersResponse:
    return ProvidersResponse(providers=model_router.available_providers())


@app.post("/v1/models/generate", response_model=GenerateResponse, tags=["models"])
def generate_model_response(payload: GenerateRequest) -> GenerateResponse:
    try:
        result = model_router.generate(
            ModelRequest(prompt=payload.prompt, task_type=payload.task_type),
            provider_name=payload.provider,
        )
    except UnknownProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(provider=result.provider, model=result.model, content=result.content)


@app.post("/v1/memory", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED, tags=["memory"])
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_service.create(payload)


@app.get("/v1/memory", response_model=MemoryListResponse, tags=["memory"])
def list_memories(category: str | None = None) -> MemoryListResponse:
    items = memory_service.list_all(category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.get("/v1/memory/search", response_model=MemoryListResponse, tags=["memory"])
def search_memories(q: str = Query(min_length=1, max_length=500), category: str | None = None) -> MemoryListResponse:
    items = memory_service.search(query=q, category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.delete("/v1/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["memory"])
def delete_memory(memory_id: UUID) -> Response:
    if not memory_service.delete(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/agents", response_model=AgentRecord, status_code=status.HTTP_201_CREATED, tags=["orchestrator"])
def register_agent(payload: AgentCreate) -> AgentRecord:
    return orchestrator_service.register_agent(payload)


@app.get("/v1/agents", response_model=AgentListResponse, tags=["orchestrator"])
def list_agents() -> AgentListResponse:
    items = orchestrator_service.list_agents()
    return AgentListResponse(items=items, count=len(items))


@app.post("/v1/tasks", response_model=TaskRecord, status_code=status.HTTP_201_CREATED, tags=["orchestrator"])
def create_task(payload: TaskCreate) -> TaskRecord:
    return orchestrator_service.create_task(payload)


@app.get("/v1/tasks", response_model=TaskListResponse, tags=["orchestrator"])
def list_tasks(task_status: TaskStatus | None = None) -> TaskListResponse:
    items = orchestrator_service.list_tasks(status=task_status)
    return TaskListResponse(items=items, count=len(items))


@app.patch("/v1/tasks/{task_id}/status", response_model=TaskRecord, tags=["orchestrator"])
def update_task_status(task_id: UUID, payload: TaskStatusUpdate) -> TaskRecord:
    task = orchestrator_service.update_task_status(task_id, payload.status)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/v1/orchestrator/assign-next", response_model=TaskRecord, tags=["orchestrator"])
def assign_next_task() -> TaskRecord:
    task = orchestrator_service.assign_next()
    if task is None:
        raise HTTPException(status_code=409, detail="No compatible task and agent available")
    return task


@app.get("/v1/orchestrator/status", response_model=OrchestratorStatus, tags=["orchestrator"])
def orchestrator_status() -> OrchestratorStatus:
    return orchestrator_service.status()