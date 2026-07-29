from fastapi.testclient import TestClient

from app.main import app
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness


def test_demo1_routes_are_registered_on_application():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.225/status' in paths
    assert '/phoenix/demo1/v21.225/run' in paths
    assert '/phoenix/demo1/v21.226/readiness' in paths


def test_readiness_reports_known_remaining_integrations():
    status = runtime_readiness()
    assert status.demo_router_registered is True
    assert status.readiness_router_registered is True
    assert status.state == 'degraded'
    assert status.autonomous_high_risk_execution_enabled is False
    assert 'real-stt-tts-adapter' in status.missing_integrations
    assert status.next_priority == 'real-stt-tts-adapter'


def test_readiness_endpoint_is_live():
    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.226/readiness')
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.226'
    assert body['demo_router_registered'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
