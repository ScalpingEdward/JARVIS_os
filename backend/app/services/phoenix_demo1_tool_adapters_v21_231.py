from app.approvals.service import approval_service
from app.memory.service import memory_service
from app.tradingview_sync.service import tradingview_sync_service
from app.voice.service import voice_control_service
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import AdapterCapability, AdapterStatus, GovernedToolInvocation, GovernedToolResult

_CAPABILITIES = [
    AdapterCapability(adapter_id='tradingview-sync', capability='status', risk='read'),
    AdapterCapability(adapter_id='tradingview-sync', capability='alerts.list', risk='read'),
    AdapterCapability(adapter_id='memory', capability='search', risk='read'),
    AdapterCapability(adapter_id='approvals', capability='list', risk='read'),
    AdapterCapability(adapter_id='voice', capability='status', risk='read'),
    AdapterCapability(adapter_id='mt5', capability='trade.execute', risk='financial', approval_required=True),
    AdapterCapability(adapter_id='browser-cdp', capability='tradingview.control', risk='write', available=False, healthy=False, approval_required=True),
]


def adapter_status() -> AdapterStatus:
    healthy = [c for c in _CAPABILITIES if c.available and c.healthy]
    unavailable = [c for c in _CAPABILITIES if not (c.available and c.healthy)]
    return AdapterStatus(capabilities=_CAPABILITIES, healthy_count=len(healthy), unavailable_count=len(unavailable))


def invoke_tool(req: GovernedToolInvocation) -> GovernedToolResult:
    match = next((c for c in _CAPABILITIES if c.adapter_id == req.adapter_id and c.capability == req.capability), None)
    if match is None:
        return GovernedToolResult(state='unsupported', adapter_id=req.adapter_id, capability=req.capability, reasons=['capability-not-registered'])
    if req.risk_brain_hard_block:
        return GovernedToolResult(state='blocked', adapter_id=req.adapter_id, capability=req.capability, reasons=['risk-brain-hard-block'])
    if not match.available or not match.healthy:
        return GovernedToolResult(state='unavailable', adapter_id=req.adapter_id, capability=req.capability, reasons=['adapter-unavailable-or-unhealthy'])
    if match.approval_required and not req.approved:
        return GovernedToolResult(state='approval-required', adapter_id=req.adapter_id, capability=req.capability, reasons=['human-approval-required'])

    if req.adapter_id == 'tradingview-sync' and req.capability == 'status':
        output = tradingview_sync_service.status().model_dump(mode='json')
    elif req.adapter_id == 'tradingview-sync' and req.capability == 'alerts.list':
        output = {'items': [item.model_dump(mode='json') for item in tradingview_sync_service.list_alerts()]}
    elif req.adapter_id == 'memory' and req.capability == 'search':
        query = str(req.arguments.get('query', '')).strip()
        category = req.arguments.get('category')
        output = {'items': [item.model_dump(mode='json') for item in memory_service.search(query, category=category)]}
    elif req.adapter_id == 'approvals' and req.capability == 'list':
        output = {'items': [item.model_dump(mode='json') for item in approval_service.list()]}
    elif req.adapter_id == 'voice' and req.capability == 'status':
        output = voice_control_service.status().model_dump(mode='json')
    elif req.adapter_id == 'mt5' and req.capability == 'trade.execute':
        return GovernedToolResult(state='blocked', adapter_id=req.adapter_id, capability=req.capability, reasons=['demo1-financial-execution-disabled'])
    else:
        return GovernedToolResult(state='unsupported', adapter_id=req.adapter_id, capability=req.capability, reasons=['no-concrete-handler'])

    return GovernedToolResult(state='completed', adapter_id=req.adapter_id, capability=req.capability, output=output)
