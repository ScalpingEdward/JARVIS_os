from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_compliance_ledger_disclosure_v21_341 import (
    _disclosure_store,
    _ledger_store,
    _package_store,
    reset_telegram_compliance_ledger_disclosure_store,
)
from app.api.routes.auron_demo1_telegram_long_term_compliance_monitoring_v21_340 import (
    _exception_store,
    _monitoring_store,
    _reattestation_store,
)
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_compliance_ledger_disclosure_store()
    _monitoring_store.clear()
    _reattestation_store.clear()
    _exception_store.clear()


def _seed_monitoring() -> str:
    monitoring_id = 'monitoring-341'
    _monitoring_store['audit-341'] = {
        'monitoring_id': monitoring_id,
        'audit_id': 'audit-341',
        'monitoring_state': 'active-compliance-monitoring',
        'baseline_evidence_hash': 'baseline-hash-341',
        'immutable': True,
        'started_at': '2026-08-03T00:00:00+00:00',
    }
    _reattestation_store[monitoring_id] = [{
        'sequence': 1,
        'reattestation_id': 'reattestation-341',
        'integrity_hash': 'reattestation-hash-341',
        'reattested_at': '2026-08-03T01:00:00+00:00',
    }]
    return monitoring_id


def test_export_sign_and_authorize_controlled_disclosure() -> None:
    monitoring_id = _seed_monitoring()
    exported = client.post('/auron/demo1/v21.341/ledger/export', json={
        'actor': 'auditor',
        'monitoring_id': monitoring_id,
        'export_phrase': 'EXPORT AURON TELEGRAM COMPLIANCE EVIDENCE LEDGER',
    })
    assert exported.status_code == 200
    ledger = exported.json()['ledger']
    assert ledger['immutable'] is True
    assert ledger['entry_count'] == 2

    signed = client.post('/auron/demo1/v21.341/package/sign', json={
        'actor': 'compliance-officer',
        'ledger_id': ledger['ledger_id'],
        'sign_phrase': 'SIGN AURON TELEGRAM REGULATOR REPORTING PACKAGE',
        'regulator': 'Supervisory Authority',
        'reporting_reference': 'REG-341',
    })
    assert signed.status_code == 200
    package = signed.json()['package']
    assert package['package_state'] == 'signed-awaiting-controlled-disclosure'

    disclosed = client.post('/auron/demo1/v21.341/disclosure/authorize', json={
        'actor': 'data-controller',
        'package_id': package['package_id'],
        'disclosure_phrase': 'AUTHORIZE AURON TELEGRAM CONTROLLED REGULATOR DISCLOSURE',
        'recipient': 'Supervisory Authority',
        'purpose': 'Statutory audit review',
        'scope': ['ledger_hash', 'entry_count', 'audit_id'],
    })
    assert disclosed.status_code == 200
    assert disclosed.json()['disclosure']['outbound_messages_sent'] == 0
    assert len(_ledger_store) == len(_package_store) == len(_disclosure_store) == 1


def test_open_regulatory_exception_blocks_export() -> None:
    monitoring_id = _seed_monitoring()
    _exception_store[monitoring_id] = {'exception_state': 'open-regulatory-exception'}
    response = client.post('/auron/demo1/v21.341/ledger/export', json={
        'actor': 'auditor',
        'monitoring_id': monitoring_id,
        'export_phrase': 'EXPORT AURON TELEGRAM COMPLIANCE EVIDENCE LEDGER',
    })
    assert response.status_code == 409


def test_invalid_disclosure_scope_fails_closed() -> None:
    monitoring_id = _seed_monitoring()
    ledger = client.post('/auron/demo1/v21.341/ledger/export', json={
        'actor': 'auditor', 'monitoring_id': monitoring_id,
        'export_phrase': 'EXPORT AURON TELEGRAM COMPLIANCE EVIDENCE LEDGER',
    }).json()['ledger']
    package = client.post('/auron/demo1/v21.341/package/sign', json={
        'actor': 'officer', 'ledger_id': ledger['ledger_id'],
        'sign_phrase': 'SIGN AURON TELEGRAM REGULATOR REPORTING PACKAGE',
        'regulator': 'Authority', 'reporting_reference': 'REG-FAIL',
    }).json()['package']
    response = client.post('/auron/demo1/v21.341/disclosure/authorize', json={
        'actor': 'controller', 'package_id': package['package_id'],
        'disclosure_phrase': 'AUTHORIZE AURON TELEGRAM CONTROLLED REGULATOR DISCLOSURE',
        'recipient': 'Authority', 'purpose': 'Review', 'scope': ['raw_certificate_secret'],
    })
    assert response.status_code == 409


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.341/ledger/export' in paths
    assert '/auron/demo1/v21.341/package/sign' in paths
    assert '/auron/demo1/v21.341/disclosure/authorize' in paths
    assert '/auron/demo1/v21.341/command-center' in paths
