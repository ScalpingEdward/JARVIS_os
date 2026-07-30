from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_launch_console_v21_236 import LaunchConsoleRequest
from app.services.phoenix_demo1_launch_console_v21_236 import build_launch_console


def test_launch_console_is_ready_after_demo1_rc1():
    result = build_launch_console(LaunchConsoleRequest())
    assert result.version == 'v21.236'
    assert result.release_candidate == 'PHOENIX-DEMO1-RC1'
    assert result.state == 'ready-to-start'
    assert result.demo1_launch_ready is True
    assert result.failed == 0
    assert result.autonomous_high_risk_execution_enabled is False
    assert result.next_action == 'start-local-runtime-and-open-operator-dashboard'


def test_launch_console_risk_brain_hard_block_is_fail_closed():
    result = build_launch_console(LaunchConsoleRequest(risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.demo1_launch_ready is False
    assert result.autonomous_high_risk_execution_enabled is False


def test_launch_console_route_is_live():
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.236/launch-console', json={})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.236'
    assert body['release_candidate'] == 'PHOENIX-DEMO1-RC1'
    assert body['startup_command'] == 'uvicorn app.main:app --host 0.0.0.0 --port 8000'
    assert body['health_endpoint'] == '/health'
