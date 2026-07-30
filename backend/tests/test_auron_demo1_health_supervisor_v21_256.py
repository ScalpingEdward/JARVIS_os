from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_health_supervisor_v21_256 import _health, dialogue
from app.main import app


def _req(command: str) -> DialogueRequest:
    return DialogueRequest(session_id='v21-256-test', workspace_id='demo', operator_id='brano', command=command)


def test_health_snapshot_contains_core_checks():
    health = _health(_req('health'))
    assert health['overall'] in {'healthy', 'degraded', 'attention-required'}
    assert 0 <= health['score'] <= 100
    assert set(health['checks']) == {'brain', 'runner', 'recovery', 'governance'}
    assert health['checks']['governance']['high_risk_approval_required'] is True
    assert health['high_risk_autonomy'] is False


def test_health_command_is_safe_and_returns_snapshot():
    result = dialogue(_req('System Health'))
    assert result['mode'] == 'health-supervisor'
    assert result['approval_required'] is False
    assert 'health' in result
    assert 'System Health:' in result['reply']


def test_command_center_and_health_route_are_registered():
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.256/command-center')
    assert response.status_code == 200
    assert 'v21.256' in response.text
    assert 'AURON HEALTH SUPERVISOR COMMAND CENTER' in response.text

    status = client.get('/auron/demo1/v21.256/health-status', params={'session_id': 'v21-256-test'})
    assert status.status_code == 200
    assert 'score' in status.json()
