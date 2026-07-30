from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import DashboardPanel, OperatorDashboardRequest, OperatorDashboardSnapshot
from app.services.phoenix_demo1_approval_inbox_v21_228 import approval_inbox_service
from app.services.phoenix_demo1_memory_binding_v21_229 import memory_binding_status
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness
from app.voice.service import voice_control_service


def build_operator_dashboard(req: OperatorDashboardRequest) -> OperatorDashboardSnapshot:
    readiness = runtime_readiness()
    approval_status = approval_inbox_service.status()
    memory_status = memory_binding_status()
    voice_status = voice_control_service.status()

    if req.risk_brain_hard_block:
        state = 'blocked'
    elif readiness.state == 'blocked':
        state = 'blocked'
    elif readiness.state == 'degraded' or approval_status.blocked > 0:
        state = 'degraded'
    else:
        state = 'ready'

    panels = [
        DashboardPanel(
            panel_id='system-readiness', title='System Readiness',
            state='blocked' if readiness.state == 'blocked' else ('degraded' if readiness.state == 'degraded' else 'ready'),
            summary=f'Demo runtime {readiness.state}; next priority: {readiness.next_priority}',
            endpoint='/phoenix/demo1/v21.226/readiness',
            attention_required=readiness.state != 'ready',
        ),
        DashboardPanel(
            panel_id='approvals', title='Approval Inbox',
            state='blocked' if approval_status.blocked else ('degraded' if approval_status.deferred else ('ready' if approval_status.pending else 'empty')),
            summary=f'{approval_status.pending} pending, {approval_status.deferred} deferred, {approval_status.blocked} blocked',
            endpoint='/phoenix/demo1/v21.228/approvals',
            attention_required=bool(approval_status.pending or approval_status.blocked),
        ),
        DashboardPanel(
            panel_id='memory', title='Memory Context',
            state='ready' if memory_status['provider_bound'] else 'degraded',
            summary=f"Provider: {memory_status['provider']}; governed retrieval enabled",
            endpoint='/phoenix/demo1/v21.229/memory/status',
            attention_required=not memory_status['provider_bound'],
        ),
        DashboardPanel(
            panel_id='voice', title='Voice Interface',
            state='ready',
            summary=f"STT {voice_status.settings.speech_to_text_provider}; TTS {voice_status.settings.text_to_speech_provider}",
            endpoint='/v1/voice/status',
            attention_required=False,
        ),
        DashboardPanel(
            panel_id='tools', title='Tool Adapters',
            state='ready' if readiness.concrete_tool_adapters_bound else 'degraded',
            summary='Concrete tool adapters bound' if readiness.concrete_tool_adapters_bound else 'Concrete tool adapters remain pending',
            endpoint='/v1/tools',
            attention_required=not readiness.concrete_tool_adapters_bound,
        ),
    ]

    if req.risk_brain_hard_block:
        for panel in panels:
            panel.state = 'blocked'
            panel.attention_required = True

    attention = [panel.panel_id for panel in panels if panel.attention_required]
    navigation = {
        'demo': '/phoenix/demo1/v21.225/status',
        'readiness': '/phoenix/demo1/v21.226/readiness',
        'voice': '/phoenix/demo1/v21.227/voice/status',
        'approvals': '/phoenix/demo1/v21.228/approvals',
        'memory': '/phoenix/demo1/v21.229/memory/status',
        'dashboard': '/phoenix/demo1/v21.230/dashboard',
        'tools': '/v1/tools',
    }
    return OperatorDashboardSnapshot(
        state=state,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        panels=panels,
        pending_approvals=approval_status.pending,
        deferred_approvals=approval_status.deferred,
        memory_provider_bound=readiness.memory_provider_bound,
        voice_adapter_bound=readiness.voice_adapter_bound,
        approval_store_persistent=readiness.approval_store_persistent,
        operator_ui_bound=True,
        concrete_tool_adapters_bound=readiness.concrete_tool_adapters_bound,
        autonomous_high_risk_execution_enabled=False,
        attention_panels=attention,
        navigation=navigation,
    )
