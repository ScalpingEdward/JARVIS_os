from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest, IntentRouteResult, PlannedCapability


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

    financial_terms = ('buy ', 'sell ', 'trade ', 'place order', 'execute trade', 'open position', 'close position')
    if _contains(text, *financial_terms):
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

    approval_required = any(item.approval_required for item in plan)
    return IntentRouteResult(
        state='planned', session_id=req.session_id, workspace_id=req.workspace_id,
        operator_id=req.operator_id, command=req.command, detected_intents=intents, plan=plan,
        approval_required=approval_required,
    )
