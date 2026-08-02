from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_dispatch_result_verification_v21_283 as verification
from app.api.routes import auron_demo1_alert_dispatch_retry_controller_v21_284 as retry
from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.api.routes import auron_demo1_controlled_alert_dispatch_adapter_v21_282 as dispatch
from app.api.routes import auron_demo1_controlled_alert_retry_dispatch_v21_285 as retry_dispatch
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    dispatch.reset_alert_dispatch_store()
    verification.reset_dispatch_result_store()
    retry.reset_retry_store()
    retry_dispatch.reset_retry_dispatch_store()


def _scheduled(monkeypatch) -> str:
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
            actor='brano', provider_status='temporary-failure', attempt=1
        ),
    )
    scheduled = retry.schedule_retry(dispatch_id, retry.RetryScheduleRequest(actor='brano', delay_seconds=60))
    return scheduled['retry']['retry_id']


def _payload(**overrides) -> retry_dispatch.ControlledRetryDispatchRequest:
    data = dict(
        actor='brano',
        adapter_registered=True,
        runtime_available=True,
        recipient_verified=True,
        force_eligible=True,
        dry_run=True,
    )
    data.update(overrides)
    return retry_dispatch.ControlledRetryDispatchRequest(**data)


def test_scheduled_retry_prepares_bounded_dry_run_without_provider_call(monkeypatch) -> None:
    result = retry_dispatch.dispatch_retry(_scheduled(monkeypatch), _payload())
    assert result['state'] == 'alert-retry-dispatch-prepared'
    assert result['retry_dispatch']['attempt'] == 2
    assert result['retry_dispatch']['dry_run'] is True
    assert result['provider_call_performed'] is False
    assert result['notification_dispatched'] is False
    assert result['external_calls_made'] == 0
    assert result['next_layer'] == 'alert-retry-result-verification'


def test_missing_runtime_blocks_retry_dispatch(monkeypatch) -> None:
    result = retry_dispatch.dispatch_retry(_scheduled(monkeypatch), _payload(runtime_available=False))
    assert result['state'] == 'alert-retry-dispatch-blocked'
    assert 'runtime_available' in result['blockers']
    assert result['provider_call_performed'] is False


def test_live_retry_dispatch_is_rejected(monkeypatch) -> None:
    retry_id = _scheduled(monkeypatch)
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.285/dispatch/{retry_id}',
        json=_payload(dry_run=False).model_dump(),
    )
    assert response.status_code == 409
    assert 'Live alert retry dispatch is not enabled' in response.json()['detail']


def test_retry_dispatch_preparation_is_idempotent(monkeypatch) -> None:
    retry_id = _scheduled(monkeypatch)
    first = retry_dispatch.dispatch_retry(retry_id, _payload())
    replay = retry_dispatch.dispatch_retry(retry_id, _payload())
    assert replay['state'] == 'alert-retry-dispatch-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['retry_dispatch']['retry_dispatch_id'] == first['retry_dispatch']['retry_dispatch_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.285/command-center')
    assert response.status_code == 200
    assert 'v21.285' in response.text
    assert 'AURON CONTROLLED ALERT RETRY DISPATCH COMMAND CENTER' in response.text
