from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_compliance_ledger_disclosure_v21_341 import (
    _disclosure_store,
    _ledger_store,
    _package_store,
)
from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import (
    TelegramRegulatorDisclosureDeliveryRequest,
    _acknowledgement_store,
    _delivery_store,
    _revocation_store,
    execute_regulator_disclosure_delivery,
    reset_telegram_regulator_disclosure_delivery_store,
)
from app.main import app


def setup_function() -> None:
    reset_telegram_regulator_disclosure_delivery_store()
    _disclosure_store.clear()
    _package_store.clear()
    _ledger_store.clear()
    _ledger_store['monitoring-1'] = {
        'ledger_id': 'ledger-1',
        'ledger_hash': 'ledger-hash',
        'ledger_state': 'immutable-compliance-evidence-ledger-exported',
    }
    _package_store['ledger-1'] = {
        'package_id': 'package-1',
        'ledger_id': 'ledger-1',
        'signature_hash': 'signature-hash',
        'package_state': 'controlled-disclosure-authorized',
        'immutable': True,
    }
    _disclosure_store['package-1'] = {
        'disclosure_id': 'disclosure-1',
        'package_id': 'package-1',
        'recipient': 'regulator@example.test',
        'purpose': 'statutory reporting',
        'scope': ['ledger_hash', 'monitoring_id'],
        'authorization_hash': 'authorization-hash',
        'immutable': True,
        'disclosure_state': 'authorized-no-transport-executed',
    }


def _deliver() -> dict:
    return execute_regulator_disclosure_delivery(
        TelegramRegulatorDisclosureDeliveryRequest(
            actor='operator',
            disclosure_id='disclosure-1',
            execution_phrase='EXECUTE AURON TELEGRAM REGULATOR DISCLOSURE DELIVERY',
        ),
        transport=lambda envelope: (True, 'provider-ref-1', None),
    )


def test_controlled_delivery_and_idempotency() -> None:
    first = _deliver()
    second = _deliver()
    assert first['delivery']['delivery_state'] == 'delivered-awaiting-recipient-acknowledgement'
    assert first['delivery']['outbound_disclosures_sent'] == 1
    assert first['delivery']['external_calls_made'] == 1
    assert second['idempotent_replay'] is True
    assert len(_delivery_store) == 1


def test_recipient_acknowledgement_and_revocation() -> None:
    delivery = _deliver()['delivery']
    client = TestClient(app)
    acknowledgement = client.post('/auron/demo1/v21.342/acknowledgement', json={
        'actor': 'recipient-control',
        'delivery_id': delivery['delivery_id'],
        'acknowledgement_phrase': 'ACKNOWLEDGE AURON TELEGRAM REGULATOR DISCLOSURE RECEIPT',
        'recipient_reference': 'regulator@example.test',
        'acknowledgement_reference': 'ACK-2026-001',
    })
    assert acknowledgement.status_code == 200
    assert acknowledgement.json()['acknowledgement']['immutable'] is True
    revocation = client.post('/auron/demo1/v21.342/revocation', json={
        'actor': 'compliance-officer',
        'delivery_id': delivery['delivery_id'],
        'revocation_phrase': 'REVOKE AURON TELEGRAM REGULATOR DISCLOSURE',
        'reason': 'Reporting authority withdrew the request',
    })
    assert revocation.status_code == 200
    assert revocation.json()['revocation']['transport_recall_guaranteed'] is False
    assert len(_acknowledgement_store) == 1
    assert len(_revocation_store) == 1


def test_delivery_fails_closed_for_invalid_authorization() -> None:
    _disclosure_store['package-1']['disclosure_state'] = 'revoked-after-delivery'
    try:
        _deliver()
        assert False, 'delivery should have been blocked'
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409


def test_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.342/status' in paths
    assert '/auron/demo1/v21.342/delivery/execute' in paths
    assert '/auron/demo1/v21.342/acknowledgement' in paths
    assert '/auron/demo1/v21.342/revocation' in paths
