from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_post_delivery_compliance_supervision_v21_343 import (
    _incident_store,
    _supervision_store,
    reset_telegram_post_delivery_compliance_supervision_store,
)
from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import (
    _acknowledgement_store,
    _delivery_store,
    _revocation_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_post_delivery_compliance_supervision_store()
    _delivery_store.clear()
    _acknowledgement_store.clear()
    _revocation_store.clear()


def _seed_delivery() -> str:
    delivery_id = 'delivery-v21-343'
    _delivery_store['disclosure-v21-343'] = {
        'delivery_id': delivery_id,
        'disclosure_id': 'disclosure-v21-343',
        'delivery_state': 'delivered-awaiting-recipient-acknowledgement',
        'accepted': True,
        'delivery_evidence_hash': 'delivery-hash',
        'immutable': True,
        'completed_at': datetime.now(timezone.utc).isoformat(),
    }
    return delivery_id


def _start() -> dict:
    delivery_id = _seed_delivery()
    response = client.post('/auron/demo1/v21.343/start', json={
        'actor': 'compliance-officer',
        'delivery_id': delivery_id,
        'start_phrase': 'START AURON TELEGRAM POST DELIVERY COMPLIANCE SUPERVISION',
        'acknowledgement_sla_hours': 24,
    })
    assert response.status_code == 200
    return response.json()['supervision']


def test_start_is_immutable_and_idempotent() -> None:
    record = _start()
    replay = client.post('/auron/demo1/v21.343/start', json={
        'actor': 'compliance-officer',
        'delivery_id': record['delivery_id'],
        'start_phrase': 'START AURON TELEGRAM POST DELIVERY COMPLIANCE SUPERVISION',
        'acknowledgement_sla_hours': 24,
    })
    assert replay.status_code == 200
    assert replay.json()['idempotent_replay'] is True
    assert record['immutable'] is True
    assert record['baseline_hash']


def test_acknowledgement_sla_breach_and_compliance() -> None:
    record = _start()
    overdue = client.post('/auron/demo1/v21.343/evaluate', json={
        'actor': 'supervisor',
        'supervision_id': record['supervision_id'],
        'evaluated_at': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    })
    assert overdue.status_code == 200
    assert overdue.json()['supervision']['supervision_state'] == 'acknowledgement-sla-breached'
    _acknowledgement_store[record['delivery_id']] = {
        'delivery_id': record['delivery_id'],
        'acknowledgement_state': 'recipient-acknowledgement-recorded',
    }
    compliant = client.post('/auron/demo1/v21.343/evaluate', json={
        'actor': 'supervisor',
        'supervision_id': record['supervision_id'],
    })
    assert compliant.json()['supervision']['supervision_state'] == 'recipient-acknowledgement-compliant'


def test_incident_and_revocation_confirmation_lifecycle() -> None:
    record = _start()
    opened = client.post('/auron/demo1/v21.343/incident/open', json={
        'actor': 'security',
        'supervision_id': record['supervision_id'],
        'incident_phrase': 'OPEN AURON TELEGRAM DISCLOSURE INCIDENT',
        'severity': 'high',
        'reason': 'Recipient reported unauthorized forwarding.',
    })
    assert opened.status_code == 200
    assert _incident_store[record['supervision_id']]['immutable'] is True
    resolved = client.post('/auron/demo1/v21.343/incident/resolve', json={
        'actor': 'security',
        'supervision_id': record['supervision_id'],
        'resolution_phrase': 'RESOLVE AURON TELEGRAM DISCLOSURE INCIDENT',
        'resolution': 'Access disabled and evidence preserved.',
    })
    assert resolved.status_code == 200
    _revocation_store[record['delivery_id']] = {
        'revocation_id': 'revocation-v21-343',
        'delivery_id': record['delivery_id'],
        'revocation_state': 'governed-disclosure-revocation-recorded',
    }
    confirmed = client.post('/auron/demo1/v21.343/revocation/confirm', json={
        'actor': 'recipient-officer',
        'supervision_id': record['supervision_id'],
        'confirmation_phrase': 'CONFIRM AURON TELEGRAM DISCLOSURE REVOCATION',
        'recipient_reference': 'REG-ACK-343',
        'confirmation_statement': 'Recipient confirms access removal; remote deletion is not asserted.',
    })
    assert confirmed.status_code == 200
    assert confirmed.json()['supervision']['supervision_state'] == 'revocation-confirmed-compliance-closed'


def test_route_registration() -> None:
    response = client.get('/auron/demo1/v21.343/status')
    assert response.status_code == 200
    assert response.json()['mode'].startswith('post-delivery-supervision')
