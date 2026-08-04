from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_seven_monitoring_v21_400 import (
    reset_telegram_successor_next_generation_seven_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_seven_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.400/monitoring/start' in paths
    assert '/auron/demo1/v21.400/health/audit' in paths
    assert '/auron/demo1/v21.400/drift/open' in paths
    assert '/auron/demo1/v21.400/drift/resolve' in paths
    assert '/auron/demo1/v21.400/status' in paths
    assert '/auron/demo1/v21.400/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.400/status')
    assert response.status_code == 200
    assert response.json() == {
        'monitoring_sessions': 0,
        'audits': 0,
        'drifts': 0,
        'resolutions': 0,
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-seven-monitoring-audit-drift-governance',
    }


def test_explicit_monitoring_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.400/monitoring/start', json={
        'actor': 'tester',
        'certification_id': 'missing-certification',
        'start_phrase': 'wrong',
        'audit_interval_days': 30,
    })
    assert response.status_code == 403


def test_certification_required_before_monitoring() -> None:
    response = client().post('/auron/demo1/v21.400/monitoring/start', json={
        'actor': 'tester',
        'certification_id': 'missing-certification',
        'start_phrase': 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION SEVEN MONITORING',
        'audit_interval_days': 30,
    })
    assert response.status_code == 409


def test_monitoring_required_before_audit() -> None:
    response = client().post('/auron/demo1/v21.400/health/audit', json={
        'actor': 'tester',
        'monitoring_id': 'missing-monitoring',
        'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN HEALTH',
        'observed_successor_next_generation_seven_hash': 'a' * 64,
        'continuity_state': 'healthy',
        'audit_reference': 'AUDIT-1',
        'audit_statement': 'audit',
    })
    assert response.status_code == 404


def test_monitoring_required_before_drift_opening() -> None:
    response = client().post('/auron/demo1/v21.400/drift/open', json={
        'actor': 'tester',
        'monitoring_id': 'missing-monitoring',
        'trigger_audit_id': 'missing-audit',
        'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT',
        'remediation_reference': 'REM-1',
    })
    assert response.status_code == 404


def test_open_drift_required_before_resolution() -> None:
    response = client().post('/auron/demo1/v21.400/drift/resolve', json={
        'actor': 'tester',
        'drift_id': 'missing-drift',
        'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN DRIFT',
        'corrected_hash': 'b' * 64,
        'control_state': 'healthy',
        'resolution_reference': 'RES-1',
        'resolution_statement': 'resolved',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.400/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SEVEN MONITORING' in response.text
    assert 'no outbound message' in response.text
