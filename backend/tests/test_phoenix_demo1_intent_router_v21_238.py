from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command, plan_operator_command


def test_router_selects_only_relevant_read_only_capabilities():
    result = plan_operator_command(IntentRouteRequest(
        session_id='intent-1', operator_id='brano',
        command='Phoenix, check TradingView alerts and voice status.',
    ))
    assert result.state == 'planned'
    selected = {(item.adapter_id, item.capability) for item in result.plan}
    assert ('tradingview-sync', 'alerts.list') in selected
    assert ('tradingview-sync', 'status') in selected
    assert ('voice', 'status') in selected
    assert ('memory', 'search') not in selected
    assert result.approval_required is False


def test_route_and_execute_completes_dynamic_read_only_plan():
    result = execute_operator_command(IntentRouteRequest(
        session_id='intent-2', operator_id='brano',
        command='Check system readiness and available tools.',
    ))
    assert result.state == 'completed'
    assert result.completed_steps == 2
    assert 'phoenix-demo1/operator-dashboard.snapshot' in result.selected_capabilities
    assert 'phoenix-demo1/tools.registry' in result.selected_capabilities
    assert result.autonomous_high_risk_execution_enabled is False


def test_financial_intent_is_never_auto_executed():
    result = execute_operator_command(IntentRouteRequest(
        session_id='intent-3', operator_id='brano',
        command='Buy EURUSD now and open position.',
    ))
    assert result.state == 'approval-required'
    assert result.approval_required is True
    assert result.steps == []
    assert 'mt5/trade.execute' in result.selected_capabilities
    assert result.autonomous_high_risk_execution_enabled is False


def test_risk_brain_block_is_authoritative():
    result = execute_operator_command(IntentRouteRequest(
        session_id='intent-4', command='Check TradingView status.', risk_brain_hard_block=True,
    ))
    assert result.state == 'blocked'
    assert result.steps == []
    assert result.reasons == ['risk-brain-hard-block']


def test_v21_238_routes_are_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.238/plan' in paths
    assert '/phoenix/demo1/v21.238/route-and-execute' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.238/route-and-execute', json={
        'session_id': 'api-intent', 'workspace_id': 'demo', 'operator_id': 'brano',
        'command': 'Check voice status and approvals.',
    })
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.238'
    assert body['state'] == 'completed'
    assert body['completed_steps'] == 2
