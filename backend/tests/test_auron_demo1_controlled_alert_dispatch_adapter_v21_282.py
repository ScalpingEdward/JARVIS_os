from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.api.routes import auron_demo1_controlled_alert_dispatch_adapter_v21_282 as dispatch
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    dispatch.reset_alert_dispatch_store()


def _prepared(monkeypatch) -> str:
    monkeypatch.setattr(delivery, '_entries', lambda: [{'integrity_verified': True}, {'integrity_verified': False}])
    result = delivery.prepare_alert_delivery(
        delivery.AlertDeliveryPrepareRequest(actor='brano', channel='email', recipient='brano@example.com')
    )
    return result['delivery']['delivery_id']


def _payload(**overrides) -> dispatch.AlertDispatchRequest:
    data = dict(actor='brano', adapter_registered=True, runtime_available=True, recipient_verified=True, dry_run=True)
    data.update(overrides)
    return dispatch.AlertDispatchRequest(**data)


def test_ready_alert_creates_dry_run_dispatch_without_external_call(monkeypatch) -> None:
    result = dispatch.dispatch_alert(_prepared(monkeypatch), _payload())
    assert result['state'] == 'alert-dispatch-prepared'
    assert result['dispatch']['adapter'] == 'email-alert-adapter'
    assert result['dispatch']['dry_run'] is True
    assert result['notification_dispatched'] is False
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_missing_readiness_blocks_dispatch(monkeypatch) -> None:
    result = dispatch.dispatch_alert(_prepared(monkeypatch), _payload(runtime_available=False))
    assert result['state'] == 'alert-dispatch-blocked'
    assert 'runtime_available' in result['blockers']
    assert result['notification_dispatched'] is False


def test_live_dispatch_is_rejected(monkeypatch) -> None:
    delivery_id = _prepared(monkeypatch)
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.282/dispatch/{delivery_id}',
        json=_payload(dry_run=False).model_dump(),
    )
    assert response.status_code == 409
    assert 'Live alert dispatch is not enabled' in response.json()['detail']


def test_dispatch_preparation_is_idempotent(monkeypatch) -> None:
    delivery_id = _prepared(monkeypatch)
    first = dispatch.dispatch_alert(delivery_id, _payload())
    replay = dispatch.dispatch_alert(delivery_id, _payload())
    assert replay['state'] == 'alert-dispatch-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['dispatch']['dispatch_id'] == first['dispatch']['dispatch_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.282/command-center')
    assert response.status_code == 200
    assert 'v21.282' in response.text
    assert 'AURON CONTROLLED ALERT DISPATCH ADAPTER COMMAND CENTER' in response.text
