from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_monitoring_v21_417 import (
    _baseline_store,
    _drift_store,
    _monitor_store,
    reset_telegram_successor_next_generation_eleven_monitoring_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_restoration_v21_416 import (
    _succession_store,
    reset_telegram_successor_next_generation_eleven_restoration_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_monitoring_v21_414 import (
    _monitor_store as _legacy_monitor_store,
    reset_telegram_successor_next_generation_ten_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_eleven_monitoring_store()
    reset_telegram_successor_next_generation_eleven_restoration_store()
    reset_telegram_successor_next_generation_ten_monitoring_store()


def seed_certification() -> str:
    legacy_monitoring_id = 'legacy-monitor-416'
    _legacy_monitor_store['cert-legacy'] = {
        'monitoring_id': legacy_monitoring_id,
        'monitoring_state': 'certified-successor-next-generation-eleven-monitoring-pending',
        'active_successor_next_generation_eleven_hash': 'a' * 64,
    }
    certification_id = 'cert-v21-416'
    _succession_store['activation-v21-416'] = {
        'certification_id': certification_id,
        'monitoring_id': legacy_monitoring_id,
        'certification_state': 'successor-next-generation-eleven-succession-certified-stable',
        'active_successor_next_generation_eleven_hash': 'a' * 64,
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return certification_id


def start_monitoring(client: TestClient) -> dict:
    response = client.post('/auron/demo1/v21.417/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': seed_certification(),
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN MONITORING',
    })
    assert response.status_code == 200
    return response.json()['monitoring']


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.417/monitoring/start' in paths
    assert '/auron/demo1/v21.417/health/audit' in paths
    assert '/auron/demo1/v21.417/drift/open' in paths
    assert '/auron/demo1/v21.417/baseline/certify' in paths
    assert '/auron/demo1/v21.417/status' in paths
    assert '/auron/demo1/v21.417/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.417/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['monitorings'] == 0


def test_monitoring_requires_explicit_phrase() -> None:
    response = build_client().post('/auron/demo1/v21.417/monitoring/start', json={
        'actor': 'master-brano',
        'certification_id': seed_certification(),
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_healthy_audit_and_baseline_certification_flow() -> None:
    client = build_client()
    monitoring = start_monitoring(client)
    audit = client.post('/auron/demo1/v21.417/health/audit', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN HEALTH',
        'observed_successor_next_generation_eleven_hash': 'a' * 64,
        'control_state': 'healthy',
        'audit_statement': 'Successor eleven is healthy.',
    })
    assert audit.status_code == 200
    assert audit.json()['audit']['healthy'] is True
    baseline = client.post('/auron/demo1/v21.417/baseline/certify', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN RENEWED BASELINE',
        'observed_successor_next_generation_eleven_hash': 'a' * 64,
        'control_state': 'healthy',
        'baseline_reference': 'BASELINE-417',
        'baseline_statement': 'Renewed baseline certified.',
    })
    assert baseline.status_code == 200
    assert len(_baseline_store) == 1


def test_hash_mismatch_fails_closed_and_allows_governed_drift() -> None:
    client = build_client()
    monitoring = start_monitoring(client)
    audit = client.post('/auron/demo1/v21.417/health/audit', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN HEALTH',
        'observed_successor_next_generation_eleven_hash': 'c' * 64,
        'control_state': 'healthy',
        'audit_statement': 'Hash mismatch detected.',
    })
    assert audit.status_code == 200
    assert audit.json()['audit']['healthy'] is False
    drift = client.post('/auron/demo1/v21.417/drift/open', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'trigger_audit_id': audit.json()['audit']['audit_id'],
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN DRIFT',
        'drift_reference': 'DRIFT-417',
        'drift_statement': 'Governed drift opened.',
    })
    assert drift.status_code == 200
    assert len(_drift_store) == 1


def test_baseline_certification_blocked_while_drift_open() -> None:
    client = build_client()
    monitoring = start_monitoring(client)
    monitoring['monitoring_state'] = 'successor-next-generation-eleven-drift-open'
    _drift_store[monitoring['monitoring_id']] = {'drift_id': 'open-drift'}
    response = client.post('/auron/demo1/v21.417/baseline/certify', json={
        'actor': 'master-brano',
        'monitoring_id': monitoring['monitoring_id'],
        'certification_phrase': 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN RENEWED BASELINE',
        'observed_successor_next_generation_eleven_hash': 'a' * 64,
        'control_state': 'healthy',
        'baseline_reference': 'BASELINE-417',
        'baseline_statement': 'Must be blocked.',
    })
    assert response.status_code == 409


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.417/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION ELEVEN MONITORING COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
