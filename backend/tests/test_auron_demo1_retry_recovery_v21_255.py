from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_retry_recovery_v21_255 import MAX_RETRIES, _recovery, _reset_recovery, dialogue, recovery_status
from app.main import app


def _req(command: str) -> DialogueRequest:
    return DialogueRequest(session_id='v21-255-test', workspace_id='demo', operator_id='brano', command=command)


def test_recovery_status_defaults_clean():
    _reset_recovery(_req('reset'))
    status = recovery_status('v21-255-test', 'demo', 'brano')
    assert status['max_retries'] == MAX_RETRIES
    assert status['retry_count'] == 0
    assert status['retryable'] is False


def test_reset_command_is_safe_and_idempotent():
    result = dialogue(_req('Retry zurücksetzen'))
    assert result['mode'] == 'recovery-reset'
    assert result['approval_required'] is False
    assert _recovery(_req('status'))['retry_count'] == 0


def test_retry_without_retryable_failure_does_not_execute():
    _reset_recovery(_req('reset'))
    result = dialogue(_req('Retry letzten Fehler'))
    assert result['mode'] == 'recovery-not-retryable'
    assert result['approval_required'] is False


def test_command_center_route_is_registered():
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.255/command-center')
    assert response.status_code == 200
    assert 'v21.255' in response.text
    assert 'RESILIENT AURON COMMAND CENTER' in response.text
