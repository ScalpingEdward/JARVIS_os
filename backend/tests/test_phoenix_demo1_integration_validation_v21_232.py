from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_integration_validation_v21_232 import DemoScenarioRequest
from app.services.phoenix_demo1_integration_validation_v21_232 import run_demo_scenario


def test_full_demo1_validation_passes():
    result = run_demo_scenario(DemoScenarioRequest())
    assert result.state == 'passed'
    assert result.acceptance_ready is True
    assert result.failed == 0
    assert result.passed >= 8
    ids = {item.check_id for item in result.checks}
    assert 'financial-execution-disabled' in ids
    assert 'tradingview-read-path' in ids


def test_risk_brain_blocks_validation_release():
    result = run_demo_scenario(DemoScenarioRequest(risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.acceptance_ready is False
    assert result.autonomous_high_risk_execution_enabled is False


def test_validation_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.232/validate' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.232/validate', json={'scenario': 'operator-readiness'})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.232'
    assert body['acceptance_ready'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
