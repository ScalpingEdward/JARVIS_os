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


def test_readiness_reports_known_remaining_integrations_after_voice_binding():
    status = runtime_readiness()
    assert status.demo_router_registered is True
    assert status.readiness_router_registered is True
    assert status.voice_adapter_bound is True
    assert status.state == 'degraded'
    assert status.autonomous_high_risk_execution_enabled is False
    assert 'real-stt-tts-adapter' not in status.missing_integrations
    assert 'persistent-approval-inbox' in status.missing_integrations
    assert status.next_priority == 'persistent-approval-inbox'


def test_readiness_endpoint_is_live():
    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.226/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.227'
    assert body['demo_router_registered'] is True
    assert body['voice_adapter_bound'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
