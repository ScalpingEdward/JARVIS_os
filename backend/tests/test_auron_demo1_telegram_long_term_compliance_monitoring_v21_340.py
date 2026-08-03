from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_erasure_audit_compliance_closure_v21_339 import _attestation_store, _audit_store, _closure_store
from app.api.routes.auron_demo1_telegram_long_term_compliance_monitoring_v21_340 import reset_telegram_long_term_compliance_monitoring_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import _certificate_store
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_long_term_compliance_monitoring_store()
    _audit_store.clear(); _attestation_store.clear(); _closure_store.clear(); _certificate_store.clear(); _go_live_store.clear()
    audit = {'audit_id': 'audit-1', 'audit_state': 'completed-compliance-closure', 'successor_certificate_id': 'cert-2', 'evidence_chain_hash': 'chain'}
    _audit_store['ret-1'] = audit
    _attestation_store['audit-1'] = {'attestation_id': 'att-1', 'attestation_state': 'independently-attested-valid-erasure-chain', 'integrity_hash': 'att-hash', 'immutable': True}
    _closure_store['audit-1'] = {'closure_id': 'close-1', 'closure_state': 'erasure-compliance-case-closed', 'integrity_hash': 'close-hash', 'immutable': True}
    _certificate_store['active'] = {'certificate_id': 'cert-2', 'certificate_state': 'certified'}
    _go_live_store['chat'] = {'service_certificate_id': 'cert-2', 'continuous_mode_active': True}


def start() -> dict:
    response = client.post('/auron/demo1/v21.340/start', json={'actor': 'auditor', 'audit_id': 'audit-1', 'start_phrase': 'START AURON TELEGRAM LONG TERM COMPLIANCE MONITORING', 'reattestation_interval_days': 30})
    assert response.status_code == 200
    return response.json()['monitoring']


def test_start_monitoring_is_immutable_and_idempotent() -> None:
    first = start()
    second = client.post('/auron/demo1/v21.340/start', json={'actor': 'auditor', 'audit_id': 'audit-1', 'start_phrase': 'START AURON TELEGRAM LONG TERM COMPLIANCE MONITORING', 'reattestation_interval_days': 30})
    assert first['immutable'] is True
    assert first['baseline_evidence_hash']
    assert second.json()['idempotent_replay'] is True


def test_periodic_evaluation_and_reattestation() -> None:
    record = start()
    response = client.post('/auron/demo1/v21.340/evaluate', json={'actor': 'auditor', 'monitoring_id': record['monitoring_id'], 'evaluated_at': '2099-01-01T00:00:00+00:00'})
    assert response.json()['reattestation_due'] is True
    response = client.post('/auron/demo1/v21.340/reattest', json={'actor': 'auditor', 'monitoring_id': record['monitoring_id'], 'reattestation_phrase': 'REATTEST AURON TELEGRAM COMPLIANCE EVIDENCE'})
    assert response.status_code == 200
    assert response.json()['reattestation']['immutable'] is True


def test_regulatory_exception_lifecycle() -> None:
    record = start()
    opened = client.post('/auron/demo1/v21.340/exception/open', json={'actor': 'compliance', 'monitoring_id': record['monitoring_id'], 'exception_phrase': 'OPEN AURON TELEGRAM REGULATORY EXCEPTION', 'authority': 'Authority', 'reference_id': 'REF-1', 'reason': 'Review required'})
    assert opened.status_code == 200
    resolved = client.post('/auron/demo1/v21.340/exception/resolve', json={'actor': 'compliance', 'monitoring_id': record['monitoring_id'], 'resolve_phrase': 'RESOLVE AURON TELEGRAM REGULATORY EXCEPTION', 'resolution': 'Resolved'})
    assert resolved.status_code == 200
    assert resolved.json()['exception']['exception_state'] == 'resolved-regulatory-exception'


def test_evidence_drift_fails_closed() -> None:
    record = start()
    _closure_store['audit-1']['integrity_hash'] = 'tampered'
    response = client.post('/auron/demo1/v21.340/evaluate', json={'actor': 'auditor', 'monitoring_id': record['monitoring_id']})
    assert response.json()['monitoring']['monitoring_state'] == 'compliance-evidence-drift-exception-required'


def test_route_registration() -> None:
    assert client.get('/auron/demo1/v21.340/status').status_code == 200
    assert client.get('/auron/demo1/v21.340/command-center').status_code == 200
