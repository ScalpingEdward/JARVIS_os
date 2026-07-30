from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_packaging_readiness_v21_234 import PackagingReadinessRequest
from app.services.phoenix_demo1_packaging_readiness_v21_234 import build_packaging_readiness


def test_packaging_readiness_is_ready_after_operator_acceptance():
    result = build_packaging_readiness(PackagingReadinessRequest())
    assert result.state == 'ready'
    assert result.operator_acceptance_ready is True
    assert result.release_packaging_ready is True
    assert result.failed == 0
    assert result.health_endpoint == '/health'
    assert 'uvicorn app.main:app' in result.startup_command
    assert result.autonomous_high_risk_execution_enabled is False


def test_package_manifest_covers_canonical_demo_surfaces():
    result = build_packaging_readiness(PackagingReadinessRequest())
    assert result.package_manifest['runtime_readiness'] == '/phoenix/demo1/v21.226/readiness'
    assert result.package_manifest['operator_acceptance'] == '/phoenix/demo1/v21.233/acceptance'
    assert result.package_manifest['tool_registry'] == '/phoenix/demo1/v21.231/tools/status'


def test_risk_brain_hard_block_prevents_release_packaging():
    result = build_packaging_readiness(PackagingReadinessRequest(risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.release_packaging_ready is False
    assert result.operator_acceptance_ready is False
    assert result.reasons == ['risk-brain-hard-block']


def test_packaging_readiness_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.234/packaging-readiness' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.234/packaging-readiness', json={})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.234'
    assert body['release_packaging_ready'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
