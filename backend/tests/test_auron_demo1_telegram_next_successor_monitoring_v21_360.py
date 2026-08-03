from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_next_successor_monitoring_v21_360 import (
    reset_telegram_next_successor_monitoring_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_next_successor_monitoring_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.360/status' in paths
    assert '/auron/demo1/v21.360/monitoring/start' in paths
    assert '/auron/demo1/v21.360/health/audit' in paths
    assert '/auron/demo1/v21.360/drift/open' in paths
    assert '/auron/demo1/v21.360/drift/resolve' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.360/status')
    assert response.status_code == 200
    body = response.json()
    assert body['monitoring_records'] == 0
    assert body['succession_health_audits'] == 0
    assert body['open_next_successor_drifts'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_start_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.360/monitoring/start', json={
        'actor': 'tester',
        'certification_id': 'missing',
        'start_phrase': 'WRONG',
        'audit_interval_days': 90,
    })
    assert response.status_code == 403


def test_missing_monitoring_blocks_audit() -> None:
    response = client.post('/auron/demo1/v21.360/health/audit', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'audit_phrase': 'AUDIT AURON TELEGRAM NEXT SUCCESSOR HEALTH',
        'observed_successor_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'audit_statement': 'healthy',
    })
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_open() -> None:
    response = client.post('/auron/demo1/v21.360/drift/open', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'open_phrase': 'OPEN AURON TELEGRAM NEXT SUCCESSOR DRIFT',
        'severity': 'high',
        'reason': 'detected mismatch',
    })
    assert response.status_code == 404
