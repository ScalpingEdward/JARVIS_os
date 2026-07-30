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
    assert '/phoenix/demo1/v21.231/tools/status' in paths
    assert '/phoenix/demo1/v21.231/tools/invoke' in paths
    assert '/phoenix/demo1/v21.232/validate' in paths
    assert '/phoenix/demo1/v21.233/acceptance' in paths
    assert '/phoenix/demo1/v21.234/packaging-readiness' in paths
    assert '/phoenix/demo1/v21.235/release-candidate' in paths


def test_readiness_reports_demo1_complete_after_v21_235():
    status = runtime_readiness()
    assert status.demo_router_registered is True
    assert status.readiness_router_registered is True
    assert status.voice_adapter_bound is True
    assert status.approval_store_persistent is True
    assert status.memory_provider_bound is True
    assert status.operator_ui_bound is True
    assert status.concrete_tool_adapters_bound is True
    assert status.state == 'ready'
    assert status.autonomous_high_risk_execution_enabled is False
    assert status.missing_integrations == []
    assert status.next_priority == 'demo1-complete'


def test_readiness_endpoint_is_live():
    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.226/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.235'
    assert body['demo_router_registered'] is True
    assert body['voice_adapter_bound'] is True
    assert body['approval_store_persistent'] is True
    assert body['memory_provider_bound'] is True
    assert body['operator_ui_bound'] is True
    assert body['concrete_tool_adapters_bound'] is True
    assert body['state'] == 'ready'
    assert body['missing_integrations'] == []
    assert body['autonomous_high_risk_execution_enabled'] is False
