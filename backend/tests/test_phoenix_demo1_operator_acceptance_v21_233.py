from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_operator_acceptance_v21_233 import OperatorAcceptanceRequest
from app.services.phoenix_demo1_operator_acceptance_v21_233 import build_operator_acceptance


def test_acceptance_builds_guided_demo_script_and_recovery_cases():
    result = build_operator_acceptance(OperatorAcceptanceRequest())
    assert result.state == 'ready'
    assert result.integration_acceptance_ready is True
    assert result.operator_acceptance_ready is True
    assert result.release_packaging_ready is False
    assert len(result.script) == 5
    assert len(result.recovery_cases) == 4
    assert result.script[-1].expected_state == 'blocked'
    assert result.autonomous_high_risk_execution_enabled is False


def test_risk_brain_hard_block_prevents_operator_acceptance():
    result = build_operator_acceptance(OperatorAcceptanceRequest(risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.operator_acceptance_ready is False
    assert 'risk-brain-hard-block' in result.reasons


def test_recovery_cases_preserve_fail_closed_and_no_auto_execution():
    result = build_operator_acceptance(OperatorAcceptanceRequest())
    cases = {item.case_id: item for item in result.recovery_cases}
    assert cases['adapter-unavailable'].expected_response == 'Invocation fails closed'
    assert cases['approval-deferred'].expected_response == 'No autonomous execution'


def test_acceptance_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.233/acceptance' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.233/acceptance', json={'workspace_id':'demo','operator_id':'operator'})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.233'
    assert body['operator_acceptance_ready'] is True
    assert body['release_packaging_ready'] is False
