from fastapi.testclient import TestClient

from app.main import app
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import GovernedToolInvocation
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness
from app.services.phoenix_demo1_tool_adapters_v21_231 import adapter_status, invoke_tool


def setup_function():
    memory_service.reset()


def test_registry_has_concrete_read_capabilities():
    status = adapter_status()
    assert status.concrete_adapters_bound is True
    ids = {(item.adapter_id, item.capability) for item in status.capabilities}
    assert ('tradingview-sync', 'status') in ids
    assert ('memory', 'search') in ids
    assert ('approvals', 'list') in ids
    assert ('voice', 'status') in ids


def test_memory_search_invokes_real_service():
    memory_service.create(MemoryCreate(content='XAUUSD London session plan', category='trading', priority=MemoryPriority.high))
    result = invoke_tool(GovernedToolInvocation(adapter_id='memory', capability='search', arguments={'query':'XAUUSD'}))
    assert result.state == 'completed'
    assert len(result.output['items']) == 1


def test_unavailable_browser_cdp_fails_closed():
    result = invoke_tool(GovernedToolInvocation(adapter_id='browser-cdp', capability='tradingview.control', approved=True))
    assert result.state == 'unavailable'


def test_financial_execution_requires_approval_then_stays_disabled_for_demo1():
    pending = invoke_tool(GovernedToolInvocation(adapter_id='mt5', capability='trade.execute'))
    assert pending.state == 'approval-required'
    approved = invoke_tool(GovernedToolInvocation(adapter_id='mt5', capability='trade.execute', approved=True))
    assert approved.state == 'blocked'
    assert 'demo1-financial-execution-disabled' in approved.reasons


def test_risk_brain_is_authoritative():
    result = invoke_tool(GovernedToolInvocation(adapter_id='memory', capability='search', arguments={'query':'gold'}, risk_brain_hard_block=True))
    assert result.state == 'blocked'


def test_routes_and_readiness_are_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.231/tools/status' in paths
    assert '/phoenix/demo1/v21.231/tools/invoke' in paths
    readiness = runtime_readiness()
    assert readiness.state == 'ready'
    assert readiness.concrete_tool_adapters_bound is True
    assert readiness.missing_integrations == []


def test_status_endpoint():
    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.231/tools/status')
    assert response.status_code == 200
    assert response.json()['concrete_adapters_bound'] is True
