from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_retry_result_verification_v21_286 as retry_verification
from app.api.routes import auron_demo1_controlled_alert_retry_dispatch_v21_285 as retry_dispatch
from app.main import app


def setup_function() -> None:
    retry_dispatch.reset_retry_dispatch_store()
    retry_verification.reset_retry_result_store()


def _retry_dispatch(attempt: int = 2, max_attempts: int = 3) -> str:
    retry_dispatch_id = 'retry-dispatch-test'
    retry_dispatch._retry_dispatch_store[retry_dispatch_id] = {
        'retry_dispatch_id': retry_dispatch_id,
        'retry_id': 'retry-1',
        'dispatch_id': 'dispatch-1',
        'delivery_id': 'delivery-1',
        'attempt': attempt,
        'max_attempts': max_attempts,
        'adapter': 'email-alert-adapter',
        'channel': 'email',
        'recipient': 'brano@example.com',
        'retry_dispatch_state': 'dry-run-prepared',
    }
    return retry_dispatch_id


def test_delivered_retry_receipt_is_terminal_and_verified() -> None:
    result = retry_verification.verify_retry_result(
        _retry_dispatch(),
        retry_verification.RetryResultVerificationRequest(
            actor='brano', provider_status='delivered', provider_receipt_id='provider-1'
        ),
    )
    assert result['state'] == 'alert-retry-result-verified'
    assert result['result']['verified'] is True
    assert result['result']['terminal'] is True
    assert result['result']['delivery_state'] == 'verified-delivered'
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_temporary_failure_before_budget_remains_retryable() -> None:
    result = retry_verification.verify_retry_result(
        _retry_dispatch(attempt=2),
        retry_verification.RetryResultVerificationRequest(
            actor='brano', provider_status='temporary-failure'
        ),
    )
    assert result['result']['retryable'] is True
    assert result['result']['terminal'] is False
    assert result['next_layer'] == 'alert-dispatch-retry-controller'


def test_temporary_failure_at_budget_is_exhausted() -> None:
    result = retry_verification.verify_retry_result(
        _retry_dispatch(attempt=3),
        retry_verification.RetryResultVerificationRequest(
            actor='brano', provider_status='temporary-failure'
        ),
    )
    assert result['result']['retryable'] is False
    assert result['result']['terminal'] is True
    assert result['result']['delivery_state'] == 'retry-exhausted'


def test_retry_result_verification_is_idempotent() -> None:
    retry_dispatch_id = _retry_dispatch()
    payload = retry_verification.RetryResultVerificationRequest(
        actor='brano', provider_status='accepted', provider_receipt_id='provider-2'
    )
    first = retry_verification.verify_retry_result(retry_dispatch_id, payload)
    replay = retry_verification.verify_retry_result(retry_dispatch_id, payload)
    assert replay['state'] == 'alert-retry-result-already-verified'
    assert replay['idempotent_replay'] is True
    assert replay['result']['result_id'] == first['result']['result_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.286/command-center')
    assert response.status_code == 200
    assert 'v21.286' in response.text
    assert 'AURON ALERT RETRY RESULT VERIFICATION COMMAND CENTER' in response.text
