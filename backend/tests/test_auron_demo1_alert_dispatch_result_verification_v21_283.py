from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.api.routes import auron_demo1_controlled_alert_dispatch_adapter_v21_282 as dispatch
from app.api.routes import auron_demo1_alert_dispatch_result_verification_v21_283 as verification
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    dispatch.reset_alert_dispatch_store()
    verification.reset_dispatch_result_store()


def _dispatch(monkeypatch) -> str:
    monkeypatch.setattr(delivery, '_entries', lambda: [{'integrity_verified': True}, {'integrity_verified': False}])
    prepared = delivery.prepare_alert_delivery(
        delivery.AlertDeliveryPrepareRequest(actor='brano', channel='email', recipient='brano@example.com')
    )
    result = dispatch.dispatch_alert(
        prepared['delivery']['delivery_id'],
        dispatch.AlertDispatchRequest(
            actor='brano', adapter_registered=True, runtime_available=True, recipient_verified=True, dry_run=True
        ),
    )
    return result['dispatch']['dispatch_id']


def test_delivered_receipt_is_terminal_and_verified(monkeypatch) -> None:
    result = verification.verify_dispatch_result(
        _dispatch(monkeypatch),
        verification.DispatchResultVerificationRequest(
            actor='brano', provider_status='delivered', provider_receipt_id='receipt-1', attempt=1
        ),
    )
    assert result['state'] == 'dispatch-result-verified'
    assert result['result']['verified'] is True
    assert result['result']['terminal'] is True
    assert result['result']['delivery_state'] == 'verified-delivered'
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_temporary_failure_is_retryable_before_limit(monkeypatch) -> None:
    result = verification.verify_dispatch_result(
        _dispatch(monkeypatch),
        verification.DispatchResultVerificationRequest(
            actor='brano', provider_status='temporary-failure', attempt=2
        ),
    )
    assert result['result']['retryable'] is True
    assert result['result']['terminal'] is False
    assert result['next_layer'] == 'alert-dispatch-retry-controller'


def test_temporary_failure_becomes_terminal_at_retry_limit(monkeypatch) -> None:
    result = verification.verify_dispatch_result(
        _dispatch(monkeypatch),
        verification.DispatchResultVerificationRequest(
            actor='brano', provider_status='temporary-failure', attempt=3
        ),
    )
    assert result['result']['retryable'] is False
    assert result['result']['terminal'] is True
    assert result['result']['delivery_state'] == 'retry-exhausted'


def test_same_dispatch_attempt_is_idempotent(monkeypatch) -> None:
    dispatch_id = _dispatch(monkeypatch)
    payload = verification.DispatchResultVerificationRequest(
        actor='brano', provider_status='accepted', provider_receipt_id='receipt-2', attempt=1
    )
    first = verification.verify_dispatch_result(dispatch_id, payload)
    replay = verification.verify_dispatch_result(dispatch_id, payload)
    assert replay['state'] == 'dispatch-result-already-verified'
    assert replay['idempotent_replay'] is True
    assert replay['result']['result_id'] == first['result']['result_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.283/command-center')
    assert response.status_code == 200
    assert 'v21.283' in response.text
    assert 'AURON ALERT DISPATCH RESULT VERIFICATION COMMAND CENTER' in response.text
