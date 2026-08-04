from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_successor_next_generation_eight_monitoring_v21_405 as module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def setup_function() -> None:
    module.reset_telegram_successor_next_generation_eight_monitoring_store()


def test_routes_registered() -> None:
    paths = {route.path for route in module.router.routes}
    assert '/auron/demo1/v21.405/monitoring/start' in paths
    assert '/auron/demo1/v21.405/health/audit' in paths
    assert '/auron/demo1/v21.405/drift/open' in paths
    assert '/auron/demo1/v21.405/drift/resolve' in paths
    assert '/auron/demo1/v21.405/status' in paths
    assert '/auron/demo1/v21.405/command-center' in paths


def test_safe_empty_status() -> None:
    response = _client().get('/auron/demo1/v21.405/status')
    assert response.status_code == 200
    assert response.json() == {
        'monitorings': 0,
        'audits': 0,
        'drifts': 0,
        'resolutions': 0,
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-eight-monitoring-audit-drift-governance',
    }


def test_monitoring_requires_explicit_phrase() -> None:
    response = _client().post(
        '/auron/demo1/v21.405/monitoring/start',
        json={
            'actor': 'tester',
            'certification_id': 'missing',
            'start_phrase': 'wrong',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 403


def test_monitoring_requires_v21_404_certification() -> None:
    response = _client().post(
        '/auron/demo1/v21.405/monitoring/start',
        json={
            'actor': 'tester',
            'certification_id': 'missing',
            'start_phrase': 'START AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION EIGHT MONITORING',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 409


def test_audit_requires_monitoring() -> None:
    response = _client().post(
        '/auron/demo1/v21.405/health/audit',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT HEALTH',
            'observed_successor_next_generation_eight_hash': 'a' * 64,
            'control_state': 'healthy',
            'audit_statement': 'healthy',
        },
    )
    assert response.status_code == 404


def test_drift_open_requires_monitoring() -> None:
    response = _client().post(
        '/auron/demo1/v21.405/drift/open',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'trigger_audit_id': 'missing',
            'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT DRIFT',
            'drift_reference': 'ref',
            'drift_statement': 'statement',
        },
    )
    assert response.status_code == 404


def test_drift_resolution_requires_open_drift() -> None:
    response = _client().post(
        '/auron/demo1/v21.405/drift/resolve',
        json={
            'actor': 'tester',
            'drift_id': 'missing',
            'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION EIGHT DRIFT',
            'corrected_successor_next_generation_eight_hash': 'a' * 64,
            'control_state': 'healthy',
            'resolution_reference': 'ref',
            'resolution_statement': 'statement',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = _client().get('/auron/demo1/v21.405/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM CERTIFIED SUCCESSOR NEXT GENERATION EIGHT MONITORING COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
