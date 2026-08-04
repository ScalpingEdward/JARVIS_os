from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_six_monitoring_v21_395 import (
    reset_telegram_successor_next_generation_six_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_six_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.395/monitoring/start' in paths
    assert '/auron/demo1/v21.395/health/audit' in paths
    assert '/auron/demo1/v21.395/drift/open' in paths
    assert '/auron/demo1/v21.395/drift/resolve' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.395/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['monitoring_records'] == 0


def test_explicit_monitoring_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.395/monitoring/start', json={
        'actor': 'operator',
        'stabilization_id': 'stabilization-1',
        'start_phrase': 'wrong',
        'audit_interval_days': 30,
    })
    assert response.status_code == 403


def test_certification_required_before_monitoring() -> None:
    response = client().post('/auron/demo1/v21.395/monitoring/start', json={
        'actor': 'operator',
        'stabilization_id': 'stabilization-1',
        'start_phrase': 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION SIX MONITORING',
        'audit_interval_days': 30,
    })
    assert response.status_code == 409


def test_monitoring_required_before_audit() -> None:
    response = client().post('/auron/demo1/v21.395/health/audit', json={
        'actor': 'operator',
        'monitoring_id': 'monitoring-1',
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX HEALTH',
        'observed_successor_next_generation_six_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'statement': 'Healthy.',
    })
    assert response.status_code == 404


def test_monitoring_required_before_drift_opening() -> None:
    response = client().post('/auron/demo1/v21.395/drift/open', json={
        'actor': 'operator',
        'monitoring_id': 'monitoring-1',
        'audit_id': 'audit-1',
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX DRIFT',
        'drift_reason': 'Hash mismatch.',
    })
    assert response.status_code == 404


def test_drift_required_before_resolution() -> None:
    response = client().post('/auron/demo1/v21.395/drift/resolve', json={
        'actor': 'operator',
        'drift_id': 'drift-1',
        'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX DRIFT',
        'corrected_successor_next_generation_six_hash': 'a' * 64,
        'control_state': 'healthy',
        'remediation_reference': 'REM-1',
        'resolution_statement': 'Resolved.',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.395/command-center')
    assert response.status_code == 200
    assert 'CERTIFIED SUCCESSOR NEXT GENERATION SIX MONITORING' in response.text
