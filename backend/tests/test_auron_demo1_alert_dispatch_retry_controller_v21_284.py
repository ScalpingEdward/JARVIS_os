from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_dispatch_result_verification_v21_283 as verification
from app.api.routes import auron_demo1_alert_dispatch_retry_controller_v21_284 as retry
from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.api.routes import auron_demo1_controlled_alert_dispatch_adapter_v21_282 as dispatch
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    dispatch.reset_alert_dispatch_store()
    verification.reset_dispatch_result_store()
    retry.reset_retry_store()


def _verified(monkeypatch, status: str = 'temporary-failure', attempt: int = 1) -> str:
    monkeypatch.setattr(delivery, '_entries', lambda: [{'integrity_verified': True}, {'integrity_verified': False}])
    prepared = delivery.prepare_alert_delivery(
        delivery.AlertDeliveryPrepareRequest(actor='brano', channel='email', recipient='brano@example.com')
    )
    dispatched = dispatch.dispatch_alert(
        prepared['delivery']['delivery_id'],
        dispatch.AlertDispatchRequest(
            actor='brano', adapter_registered=True, runtime_available=True, recipient_verified=True, dry_run=True
        ),
    )
    dispatch_id = dispatched['dispatch']['dispatch_id']
    verification.verify_dispatch_result(
        dispatch_id,
        verification.DispatchResultVerificationRequest(
            actor='brano', provider_status=status, attempt=attempt
        ),
    )
    return dispatch_id


def test_retryable_failure_schedules_next_attempt_without_provider_call(monkeypatch) -> None:
    result = retry.schedule_retry(
        _verified(monkeypatch),
        retry.RetryScheduleRequest(actor='brano', delay_seconds=45),
    )
    assert result['state'] == 'alert-retry-scheduled'
    assert result['retry']['attempt'] == 2
    assert result['retry']['attempts_remaining_after_schedule'] == 1
    assert result['retry']['provider_call_performed'] is False
    assert result['external_calls_made'] == 0
    assert result['next_layer'] == 'controlled-alert-retry-dispatch'


def test_same_attempt_schedule_is_idempotent(monkeypatch) -> None:
    dispatch_id = _verified(monkeypatch)
    payload = retry.RetryScheduleRequest(actor='brano')
    first = retry.schedule_retry(dispatch_id, payload)
    replay = retry.schedule_retry(dispatch_id, payload)
    assert replay['state'] == 'alert-retry-already-scheduled'
    assert replay['idempotent_replay'] is True
    assert replay['retry']['retry_id'] == first['retry']['retry_id']


def test_terminal_result_cannot_be_retried(monkeypatch) -> None:
    dispatch_id = _verified(monkeypatch, status='permanent-failure')
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.284/schedule/{dispatch_id}',
        json={'actor': 'brano', 'delay_seconds': 30},
    )
    assert response.status_code == 409
    assert 'not retryable' in response.json()['detail']


def test_retry_budget_is_enforced(monkeypatch) -> None:
    dispatch_id = _verified(monkeypatch, status='temporary-failure', attempt=3)
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.284/schedule/{dispatch_id}',
        json={'actor': 'brano', 'delay_seconds': 30},
    )
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.284/command-center')
    assert response.status_code == 200
    assert 'v21.284' in response.text
    assert 'AURON ALERT DISPATCH RETRY CONTROLLER COMMAND CENTER' in response.text
