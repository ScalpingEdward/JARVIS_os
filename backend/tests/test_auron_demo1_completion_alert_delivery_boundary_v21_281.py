from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()


def _warning_entries() -> list[dict]:
    return [
        {'integrity_verified': True},
        {'integrity_verified': False},
    ]


def test_prepare_creates_non_dispatched_delivery(monkeypatch) -> None:
    monkeypatch.setattr(delivery, '_entries', _warning_entries)
    result = delivery.prepare_alert_delivery(
        delivery.AlertDeliveryPrepareRequest(actor='brano', channel='operator-console', recipient='brano')
    )

    assert result['state'] == 'alert-delivery-prepared'
    assert result['delivery_prepared'] is True
    assert result['deduplicated'] is False
    assert result['delivery']['severity'] == 'warning'
    assert result['delivery']['notification_dispatched'] is False
    assert result['external_calls_made'] == 0
    assert result['business_mutations_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_prepare_deduplicates_same_active_signal(monkeypatch) -> None:
    monkeypatch.setattr(delivery, '_entries', _warning_entries)
    payload = delivery.AlertDeliveryPrepareRequest(actor='brano', channel='operator-console', recipient='brano')

    first = delivery.prepare_alert_delivery(payload)
    second = delivery.prepare_alert_delivery(payload)

    assert second['state'] == 'alert-delivery-deduplicated'
    assert second['deduplicated'] is True
    assert second['delivery']['delivery_id'] == first['delivery']['delivery_id']
    assert len(delivery._delivery_store) == 1


def test_acknowledgement_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(delivery, '_entries', _warning_entries)
    prepared = delivery.prepare_alert_delivery(
        delivery.AlertDeliveryPrepareRequest(actor='brano', recipient='brano')
    )
    delivery_id = prepared['delivery']['delivery_id']
    payload = delivery.AlertAcknowledgementRequest(actor='brano', note='seen')

    first = delivery.acknowledge_alert_delivery(delivery_id, payload)
    replay = delivery.acknowledge_alert_delivery(delivery_id, payload)

    assert first['state'] == 'alert-delivery-acknowledged'
    assert first['delivery']['acknowledged'] is True
    assert replay['state'] == 'alert-delivery-already-acknowledged'
    assert replay['idempotent_replay'] is True
    assert replay['external_calls_made'] == 0


def test_no_delivery_when_policy_is_ok(monkeypatch) -> None:
    monkeypatch.setattr(delivery, '_entries', lambda: [{'integrity_verified': True}])
    result = delivery.prepare_alert_delivery(delivery.AlertDeliveryPrepareRequest(actor='brano'))

    assert result['state'] == 'no-alert-delivery-required'
    assert result['delivery_prepared'] is False
    assert len(delivery._delivery_store) == 0


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.281/command-center')

    assert response.status_code == 200
    assert 'v21.281' in response.text
    assert 'AURON COMPLETION ALERT DELIVERY BOUNDARY COMMAND CENTER' in response.text
