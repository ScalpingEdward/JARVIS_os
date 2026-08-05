from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_monitoring_v21_417 import (
    _monitor_store as _legacy_monitor_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_twelve_restoration_v21_419 import (
    _succession_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_twelve_monitoring_v21_420 import (
    reset_telegram_successor_next_generation_twelve_monitoring_store,
    router,
)

HASH = 'a' * 64
BAD_HASH = 'b' * 64
CERTIFICATION_ID = 'cert-twelve'
LEGACY_MONITORING_ID = 'legacy-monitor-twelve'


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def seed_certification() -> None:
    _succession_store.clear()
    _legacy_monitor_store.clear()
    _succession_store['activation-twelve'] = {
        'certification_id': CERTIFICATION_ID,
        'monitoring_id': LEGACY_MONITORING_ID,
        'active_successor_next_generation_twelve_hash': HASH,
        'certification_state': 'successor-next-generation-twelve-succession-certified-stable',
        'integrity_hash': 'evidence',
        'immutable': True,
    }
    _legacy_monitor_store['legacy-key'] = {
        'monitoring_id': LEGACY_MONITORING_ID,
        'monitoring_state': 'certified-successor-next-generation-twelve-monitoring-pending',
        'active_successor_next_generation_twelve_hash': HASH,
    }


def start_monitoring(api: TestClient) -> dict:
    response = api.post('/auron/demo1/v21.420/monitoring/start', json={
        'actor': 'test-operator',
        'certification_id': CERTIFICATION_ID,
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE MONITORING',
        'audit_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['monitoring']


def setup_function() -> None:
    reset_telegram_successor_next_generation_twelve_monitoring_store()
    _succession_store.clear()
    _legacy_monitor_store.clear()


def test_routes_registered_and_empty_status_safe() -> None:
    api = client()
    status = api.get('/auron/demo1/v21.420/status')
    assert status.status_code == 200
    assert status.json() == {
        'monitorings': 0,
        'audits': 0,
        'drifts': 0,
        'renewed_baselines': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-twelve-monitoring-drift-renewed-baseline-certification',
    }


def test_explicit_monitoring_phrase_required() -> None:
    seed_certification()
    response = client().post('/auron/demo1/v21.420/monitoring/start', json={
        'actor': 'test-operator',
        'certification_id': CERTIFICATION_ID,
        'start_phrase': 'WRONG PHRASE',
        'audit_interval_days': 30,
    })
    assert response.status_code == 403


def test_healthy_audit_and_renewed_baseline_certification_flow() -> None:
    seed_certification()
    api = client()
    monitoring = start_monitoring(api)
    monitoring_id = monitoring['monitoring_id']

    audit = api.post('/auron/demo1/v21.420/health/audit', json={
        'actor': 'auditor',
        'monitoring_id': monitoring_id,
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE HEALTH',
        'observed_successor_next_generation_twelve_hash': HASH,
        'control_state': 'healthy',
        'audit_statement': 'All controls healthy and hash aligned.',
    })
    assert audit.status_code == 200
    assert audit.json()['audit']['healthy'] is True
    assert audit.json()['external_calls_made'] == 0

    baseline = api.post('/auron/demo1/v21.420/baseline/certify', json={
        'actor': 'certifier',
        'monitoring_id': monitoring_id,
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE RENEWED BASELINE',
        'observed_successor_next_generation_twelve_hash': HASH,
        'control_state': 'healthy',
        'baseline_reference': 'baseline-12',
        'baseline_statement': 'Renewed baseline certified after healthy monitoring.',
    })
    assert baseline.status_code == 200
    body = baseline.json()
    assert body['baseline']['baseline_state'] == 'successor-next-generation-twelve-renewed-baseline-certified-active'
    assert body['baseline']['immutable'] is True
    assert body['external_calls_made'] == 0


def test_hash_mismatch_fails_closed_and_allows_governed_drift_opening() -> None:
    seed_certification()
    api = client()
    monitoring_id = start_monitoring(api)['monitoring_id']

    audit = api.post('/auron/demo1/v21.420/health/audit', json={
        'actor': 'auditor',
        'monitoring_id': monitoring_id,
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE HEALTH',
        'observed_successor_next_generation_twelve_hash': BAD_HASH,
        'control_state': 'healthy',
        'audit_statement': 'Observed hash mismatch.',
    })
    assert audit.status_code == 200
    audit_body = audit.json()
    assert audit_body['audit']['healthy'] is False
    assert audit_body['monitoring']['monitoring_state'] == 'successor-next-generation-twelve-drift-detected'

    drift = api.post('/auron/demo1/v21.420/drift/open', json={
        'actor': 'governance',
        'monitoring_id': monitoring_id,
        'trigger_audit_id': audit_body['audit']['audit_id'],
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE DRIFT',
        'drift_reference': 'drift-12',
        'drift_statement': 'Open governed drift from immutable failed audit.',
    })
    assert drift.status_code == 200
    assert drift.json()['drift']['drift_state'] == 'successor-next-generation-twelve-drift-open'
    assert drift.json()['external_calls_made'] == 0

    blocked = api.post('/auron/demo1/v21.420/baseline/certify', json={
        'actor': 'certifier',
        'monitoring_id': monitoring_id,
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE RENEWED BASELINE',
        'observed_successor_next_generation_twelve_hash': HASH,
        'control_state': 'healthy',
        'baseline_reference': 'blocked',
        'baseline_statement': 'Must not certify while drift is open.',
    })
    assert blocked.status_code == 409


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.420/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM SUCCESSOR NEXT GENERATION TWELVE MONITORING COMMAND CENTER' in response.text
    assert 'no Telegram API call' in response.text
