from fastapi.testclient import TestClient

from app.main import app
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness


def test_demo1_routes_are_registered_on_application():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.225/status' in paths
    assert '/phoenix/demo1/v21.225/run' in paths
    assert '/phoenix/demo1/v21.226/readiness' in paths
    assert '/phoenix/demo1/v21.227/voice/status' in paths
    assert '/phoenix/demo1/v21.227/voice/resolve' in paths
    assert '/phoenix/demo1/v21.228/approvals/status' in paths
    assert '/phoenix/demo1/v21.228/approvals' in paths
    assert '/phoenix/demo1/v21.228/approvals/recover-deferred' in paths
    assert '/phoenix/demo1/v21.229/memory/status' in paths
    assert '/phoenix/demo1/v21.229/memory/context' in paths
    assert '/phoenix/demo1/v21.230/dashboard' in paths


def test_readiness_reports_only_tool_adapter_debt_after_dashboard_binding():
    status = runtime_readiness()
    assert status.demo_router_registered is True
    assert status.readiness_router_registered is True
    assert status.voice_adapter_bound is True
    assert status.approval_store_persistent is True
    assert status.memory_provider_bound is True
    assert status.operator_ui_bound is True
    assert status.concrete_tool_adapters_bound is False
    assert status.state == 'degraded'
    assert status.autonomous_high_risk_execution_enabled is False
    assert 'operator-ui-dashboard' not in status.missing_integrations
    assert status.missing_integrations == ['concrete-tool-adapters']
    assert status.next_priority == 'concrete-tool-adapters'


def test_readiness_endpoint_is_live():
    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.226/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.230'
    assert body['demo_router_registered'] is True
    assert body['voice_adapter_bound'] is True
    assert body['approval_store_persistent'] is True
    assert body['memory_provider_bound'] is True
    assert body['operator_ui_bound'] is True
    assert body['concrete_tool_adapters_bound'] is False
    assert body['autonomous_high_risk_execution_enabled'] is False
