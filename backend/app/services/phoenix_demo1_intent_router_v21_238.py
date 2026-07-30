from app.schemas.phoenix_demo1_intent_router_v21_238 import (
    DynamicExecutionStep,
    DynamicIntentExecutionResult,
    IntentRouteRequest,
    IntentRouteResult,
    PlannedCapability,
)
from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import OperatorDashboardRequest
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import GovernedToolInvocation
from app.services.phoenix_demo1_operator_dashboard_v21_230 import build_operator_dashboard
from app.services.phoenix_demo1_tool_adapters_v21_231 import adapter_status, invoke_tool


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def plan_operator_command(req: IntentRouteRequest) -> IntentRouteResult:
    if req.risk_brain_hard_block:
        return IntentRouteResult(
            state='blocked', session_id=req.session_id, workspace_id=req.workspace_id,
            operator_id=req.operator_id, command=req.command, detected_intents=[], plan=[],
            reasons=['risk-brain-hard-block'],
        )

    text = req.command.lower().strip()
    intents: list[str] = []
    plan: list[PlannedCapability] = []

    def add(intent: str, step_id: str, adapter_id: str, capability: str, reason: str, arguments: dict | None = None):
        if intent not in intents:
            intents.append(intent)
        if not any(item.adapter_id == adapter_id and item.capability == capability for item in plan):
            plan.append(PlannedCapability(
                step_id=step_id, intent=intent, adapter_id=adapter_id, capability=capability,
                arguments=arguments or {}, reason=reason,
            ))

    if _contains(text, 'system', 'readiness', 'status', 'health', 'ready'):
        add('system-status', 'system-readiness', 'phoenix-demo1', 'operator-dashboard.snapshot', 'Command asks for system/runtime readiness.')
    if _contains(text, 'memory', 'remember', 'erinner', 'context', 'search memory'):
        add('memory-search', 'memory-search', 'memory', 'search', 'Command asks for memory/context retrieval.', {'query': req.command})
    if _contains(text, 'voice', 'speech', 'stt', 'tts', 'sprache', 'stimme'):
        add('voice-status', 'voice-status', 'voice', 'status', 'Command references voice or speech capability.')
    if _contains(text, 'approval', 'approve', 'freigabe', 'pending'):
        add('approval-inbox', 'approval-inbox', 'approvals', 'list', 'Command asks about approvals or pending requests.')
    if _contains(text, 'tradingview', 'chart', 'alert', 'alerts'):
        if _contains(text, 'alert', 'alerts'):
            add('tradingview-alerts', 'tradingview-alerts', 'tradingview-sync', 'alerts.list', 'Command asks for TradingView alerts.')
        add('tradingview-status', 'tradingview-status', 'tradingview-sync', 'status', 'Command references TradingView/chart state.')
    if _contains(text, 'tool', 'tools', 'adapter', 'capabilit'):
        add('tool-registry', 'tool-registry', 'phoenix-demo1', 'tools.registry', 'Command asks for available tools/capabilities.')

    if _contains(text, 'buy ', 'sell ', 'trade ', 'place order', 'execute trade', 'open position', 'close position'):
        intents.append('financial-execution')
        plan.append(PlannedCapability(
            step_id='financial-execution', intent='financial-execution', adapter_id='mt5', capability='trade.execute',
            risk='financial', approval_required=True, reason='Command requests financial execution; human approval is mandatory.',
        ))

    if not plan:
        return IntentRouteResult(
            state='unsupported', session_id=req.session_id, workspace_id=req.workspace_id,
            operator_id=req.operator_id, command=req.command, detected_intents=[], plan=[],
            reasons=['no-supported-demo1-intent-detected'],
        )

    return IntentRouteResult(
        state='planned', session_id=req.session_id, workspace_id=req.workspace_id,
        operator_id=req.operator_id, command=req.command, detected_intents=intents, plan=plan,
        approval_required=any(item.approval_required for item in plan),
    )


def execute_operator_command(req: IntentRouteRequest) -> DynamicIntentExecutionResult:
    route = plan_operator_command(req)
    if route.state != 'planned':
        return DynamicIntentExecutionResult(
            state=route.state, session_id=req.session_id, workspace_id=req.workspace_id,
            operator_id=req.operator_id, command=req.command, detected_intents=route.detected_intents,
            selected_capabilities=[], steps=[], approval_required=route.approval_required,
            operator_summary='Command blocked.' if route.state == 'blocked' else 'No supported Demo 1 intent detected.',
            reasons=route.reasons,
        )

    if route.approval_required:
        return DynamicIntentExecutionResult(
            state='approval-required', session_id=req.session_id, workspace_id=req.workspace_id,
            operator_id=req.operator_id, command=req.command, detected_intents=route.detected_intents,
            selected_capabilities=[f'{p.adapter_id}/{p.capability}' for p in route.plan], steps=[],
            approval_required=True, operator_summary='Human approval required before financial/high-risk execution.',
            reasons=['human-approval-required'],
        )

    steps: list[DynamicExecutionStep] = []
    for planned in route.plan:
        if planned.adapter_id == 'phoenix-demo1' and planned.capability == 'operator-dashboard.snapshot':
            dashboard = build_operator_dashboard(OperatorDashboardRequest(
                workspace_id=req.workspace_id, operator_id=req.operator_id, risk_brain_hard_block=False,
            ))
            steps.append(DynamicExecutionStep(
                step_id=planned.step_id, intent=planned.intent, adapter_id=planned.adapter_id,
                capability=planned.capability, state='completed', output=dashboard.model_dump(mode='json'),
            ))
            continue
        if planned.adapter_id == 'phoenix-demo1' and planned.capability == 'tools.registry':
            registry = adapter_status()
            steps.append(DynamicExecutionStep(
                step_id=planned.step_id, intent=planned.intent, adapter_id=planned.adapter_id,
                capability=planned.capability, state='completed', output=registry.model_dump(mode='json'),
            ))
            continue

        result = invoke_tool(GovernedToolInvocation(
            adapter_id=planned.adapter_id, capability=planned.capability, arguments=planned.arguments,
            approved=False, risk_brain_hard_block=False,
        ))
        steps.append(DynamicExecutionStep(
            step_id=planned.step_id, intent=planned.intent, adapter_id=planned.adapter_id,
            capability=planned.capability, state=result.state, output=result.output, reasons=result.reasons,
        ))

    completed = sum(1 for step in steps if step.state == 'completed')
    failed = len(steps) - completed
    state = 'completed' if failed == 0 else ('partial' if completed else 'failed')
    selected = [f'{p.adapter_id}/{p.capability}' for p in route.plan]
    summary = f'PHOENIX routed intents={",".join(route.detected_intents)}; selected={len(selected)}; completed={completed}/{len(steps)}; result={state}.'
    return DynamicIntentExecutionResult(
        state=state, session_id=req.session_id, workspace_id=req.workspace_id,
        operator_id=req.operator_id, command=req.command, detected_intents=route.detected_intents,
        selected_capabilities=selected, steps=steps, completed_steps=completed,
        approval_required=False, operator_summary=summary,
        reasons=[] if state == 'completed' else ['one-or-more-selected-capabilities-not-completed'],
    )
