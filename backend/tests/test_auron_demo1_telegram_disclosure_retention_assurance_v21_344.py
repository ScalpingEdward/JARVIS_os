from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_disclosure_retention_assurance_v21_344 import (
    _assurance_store,
    _attestation_store,
    _exception_store,
    _retention_store,
    reset_telegram_disclosure_retention_assurance_store,
)
from app.api.routes.auron_demo1_telegram_post_delivery_compliance_supervision_v21_343 import (
    _incident_store,
    _supervision_store,
)
from app.api.routes.auron_demo1_telegram_regulator_disclosure_delivery_v21_342 import (
    _acknowledgement_store,
    _delivery_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_disclosure_retention_assurance_store()
    _supervision_store.clear()
    _incident_store.clear()
    _delivery_store.clear()
    _acknowledgement_store.clear()
    now = datetime.now(timezone.utc).isoformat()
    _delivery_store['disc-1'] = {
        'delivery_id': 'delivery-1',
        'disclosure_id': 'disc-1',
        'delivery_state': 'delivered-recipient-acknowledged',
        'accepted': True,
        'delivery_evidence_hash': 'delivery-hash-1',
        'immutable': True,
        'completed_at': now,
    }
    _acknowledgement_store['delivery-1'] = {
        'acknowledgement_id': 'ack-1',
        'delivery_id': 'delivery-1',
        'acknowledgement_state': 'recipient-acknowledgement-recorded',
    }
    _supervision_store['delivery-1'] = {
        'supervision_id': 'supervision-1',
        'delivery_id': 'delivery-1',
        'disclosure_id': 'disc-1',
        'delivery_evidence_hash': 'delivery-hash-1',
        'supervision_state': 'recipient-acknowledgement-compliant',
        'immutable': True,
    }


def establish() -> dict:
    response = client.post('/auron/demo1/v21.344/retention/establish', json={
        'actor': 'compliance-owner',
        'supervision_id': 'supervision-1',
        'establishment_phrase': 'ESTABLISH AURON TELEGRAM DISCLOSURE RETENTION CONTROL',
        'recipient_retention_days': 30,
        'assurance_interval_days': 7,
    })
    assert response.status_code == 200
    return response.json()['retention']


def test_retention_establishment_is_immutable_and_idempotent() -> None:
    first = establish()
    second = establish()
    assert first['retention_state'] == 'active-recipient-retention-control'
    assert first['immutable'] is True
    assert first['baseline_hash']
    assert second['retention_id'] == first['retention_id']
    assert len(_retention_store) == 1


def test_assurance_revalidation_and_downstream_attestation() -> None:
    retention = establish()
    assurance = client.post('/auron/demo1/v21.344/assurance/revalidate', json={
        'actor': 'recipient-assurance-owner',
        'retention_id': retention['retention_id'],
        'revalidation_phrase': 'REVALIDATE AURON TELEGRAM RECIPIENT ASSURANCE',
        'assurance_reference': 'ASSURANCE-2026-001',
        'control_statement': 'Recipient confirms access control, purpose limitation and audit logging remain effective.',
    })
    assert assurance.status_code == 200
    assert assurance.json()['assurance']['sequence'] == 1
    attestation = client.post('/auron/demo1/v21.344/downstream/attest', json={
        'actor': 'processor-auditor',
        'retention_id': retention['retention_id'],
        'attestation_phrase': 'ATTEST AURON TELEGRAM DOWNSTREAM DATA HANDLING',
        'processor_name': 'Regulatory Processor GmbH',
        'purpose_limitation_statement': 'Processing remains limited to the authorized regulatory purpose.',
        'deletion_or_return_commitment': 'Data will be deleted or returned when retention expires.',
    })
    assert attestation.status_code == 200
    assert attestation.json()['attestation']['attestation_state'] == 'downstream-data-handling-attested'
    assert len(_assurance_store[retention['retention_id']]) == 1
    assert retention['retention_id'] in _attestation_store


def test_retention_expiry_and_assurance_due_evaluation() -> None:
    retention = establish()
    due = client.post('/auron/demo1/v21.344/retention/evaluate', json={
        'actor': 'scheduler',
        'retention_id': retention['retention_id'],
        'evaluated_at': (datetime.now(timezone.utc) + timedelta(days=8)).isoformat(),
    })
    assert due.status_code == 200
    assert due.json()['assurance_due'] is True
    expired = client.post('/auron/demo1/v21.344/retention/evaluate', json={
        'actor': 'scheduler',
        'retention_id': retention['retention_id'],
        'evaluated_at': (datetime.now(timezone.utc) + timedelta(days=31)).isoformat(),
    })
    assert expired.status_code == 200
    assert expired.json()['retention_expired'] is True
    assert expired.json()['retention']['retention_state'] == 'recipient-retention-expired-return-or-deletion-due'


def test_exception_blocks_assurance_until_resolved() -> None:
    retention = establish()
    opened = client.post('/auron/demo1/v21.344/exception/open', json={
        'actor': 'compliance-owner',
        'retention_id': retention['retention_id'],
        'exception_phrase': 'OPEN AURON TELEGRAM DOWNSTREAM HANDLING EXCEPTION',
        'severity': 'high',
        'reason': 'Recipient assurance evidence is incomplete.',
    })
    assert opened.status_code == 200
    blocked = client.post('/auron/demo1/v21.344/assurance/revalidate', json={
        'actor': 'recipient-assurance-owner',
        'retention_id': retention['retention_id'],
        'revalidation_phrase': 'REVALIDATE AURON TELEGRAM RECIPIENT ASSURANCE',
        'assurance_reference': 'ASSURANCE-2026-002',
        'control_statement': 'Updated assurance statement.',
    })
    assert blocked.status_code == 409
    resolved = client.post('/auron/demo1/v21.344/exception/resolve', json={
        'actor': 'compliance-owner',
        'retention_id': retention['retention_id'],
        'resolution_phrase': 'RESOLVE AURON TELEGRAM DOWNSTREAM HANDLING EXCEPTION',
        'resolution': 'Missing evidence was supplied and independently reviewed.',
    })
    assert resolved.status_code == 200
    assert _exception_store[retention['retention_id']]['exception_state'] == 'resolved-downstream-handling-exception'


def test_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.344/retention/establish' in paths
    assert '/auron/demo1/v21.344/assurance/revalidate' in paths
    assert '/auron/demo1/v21.344/downstream/attest' in paths
    assert '/auron/demo1/v21.344/command-center' in paths
