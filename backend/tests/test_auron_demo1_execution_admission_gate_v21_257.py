from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_execution_admission_gate_v21_257 import MIN_SAFE_SCORE, _admission, dialogue
from app.main import app


def _req(command: str = 'execution gate') -> DialogueRequest:
    return DialogueRequest(session_id='v21-257-test', workspace_id='demo', operator_id='brano', command=command)


def test_admission_snapshot_has_governed_shape():
    result = _admission(_req())
    assert result['classification'] in {'admitted', 'denied'}
    assert isinstance(result['health_score'], int)
    assert result['low_risk_only'] is True
    assert result['high_risk_autonomy'] is False
    if result['allowed']:
        assert result['health_score'] >= MIN_SAFE_SCORE


def test_execution_gate_status_is_read_only():
    result = dialogue(_req('Execution Gate'))
    assert result['mode'] == 'execution-admission-status'
    assert result['approval_required'] is False
    assert 'admission' in result


def test_command_center_route_is_registered():
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.257/command-center')
    assert response.status_code == 200
    assert 'v21.257' in response.text
    assert 'AURON EXECUTION ADMISSION COMMAND CENTER' in response.text
