from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_three_monitoring_v21_380 import (
    reset_telegram_successor_next_generation_three_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_three_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.380/monitoring/start' in paths
    assert '/auron/demo1/v21.380/health/audit' in paths
    assert '/auron/demo1/v21.380/drift/open' in paths
    assert '/auron/demo1/v21.380/drift/resolve' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.380/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['monitoring_records'] == 0


def test_explicit_monitoring_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.380/monitoring/start', json={
        'actor': 'tester',
        'continuity_monitor_id': 'missing',
        'start_phrase': 'WRONG',
        'audit_interval_days': 30,
    })
    assert response.status_code == 403


def test_missing_monitoring_audit_blocked() -> None:
    response = client().post('/auron/demo1/v21.380/health/audit', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE HEALTH',
        'observed_successor_next_generation_three_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'statement': 'check',
    })
    assert response.status_code == 404


def test_missing_monitoring_drift_open_blocked() -> None:
    response = client().post('/auron/demo1/v21.380/drift/open', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'drift_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE DRIFT',
        'trigger_audit_id': 'missing',
        'reason': 'check',
    })
    assert response.status_code == 404


def test_missing_monitoring_drift_resolution_blocked() -> None:
    response = client().post('/auron/demo1/v21.380/drift/resolve', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE DRIFT',
        'corrected_successor_next_generation_three_hash': 'b' * 64,
        'control_state': 'healthy',
        'remediation_reference': 'ref',
        'remediation_statement': 'done',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.380/command-center')
    assert response.status_code == 200
    assert 'CERTIFIED SUCCESSOR NEXT GENERATION THREE MONITORING' in response.text
