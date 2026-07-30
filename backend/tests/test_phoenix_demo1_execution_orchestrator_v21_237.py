from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_execution_orchestrator_v21_237 import ExecutionOrchestratorRequest
from app.services.phoenix_demo1_execution_orchestrator_v21_237 import execute_demo_command


def test_execution_orchestrator_completes_read_only_operator_status_command():
    result = execute_demo_command(ExecutionOrchestratorRequest(
        session_id='demo-session-001',
        workspace_id='demo',
        operator_id='brano',
        command='Check system readiness, memory, voice, approvals and available tools. Return a concise operator status summary.',
    ))
    assert result.version == 'v21.237'
    assert result.state in {'completed', 'partial'}
    assert result.completed_steps >= 5
    assert result.approval_required is False
    assert result.autonomous_high_risk_execution_enabled is False
    assert result.audit_digest
    assert 'PHOENIX execution complete' in result.operator_summary


def test_execution_orchestrator_risk_brain_hard_block_is_authoritative():
    result = execute_demo_command(ExecutionOrchestratorRequest(
        session_id='blocked-session',
        command='Check status',
        risk_brain_hard_block=True,
    ))
    assert result.state == 'blocked'
    assert result.steps == []
    assert result.reasons == ['risk-brain-hard-block']
    assert result.autonomous_high_risk_execution_enabled is False


def test_execution_orchestrator_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.237/execute' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.237/execute', json={
        'session_id': 'api-demo-session',
        'workspace_id': 'demo',
        'operator_id': 'operator',
        'command': 'Check system readiness and available tools.',
    })
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.237'
    assert body['state'] in ['completed', 'partial']
    assert body['autonomous_high_risk_execution_enabled'] is False
