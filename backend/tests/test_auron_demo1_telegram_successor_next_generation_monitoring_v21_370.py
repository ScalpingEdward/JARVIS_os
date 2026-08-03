from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_monitoring_v21_370 import (
    reset_telegram_successor_next_generation_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.370/monitoring/start' in paths
    assert '/auron/demo1/v21.370/health/audit' in paths
    assert '/auron/demo1/v21.370/drift/open' in paths
    assert '/auron/demo1/v21.370/drift/resolve' in paths
    assert '/auron/demo1/v21.370/status' in paths
    assert '/auron/demo1/v21.370/command-center' in paths


def test_status_is_safe_and_empty() -> None:
    response = client().get('/auron/demo1/v21.370/status')
    assert response.status_code == 200
    assert response.json() == {
        'monitoring_records': 0,
        'health_audits': 0,
        'open_drifts': 0,
        'drift_resolutions': 0,
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-monitoring-health-audit-drift-governance',
    }


def test_monitoring_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.370/monitoring/start',
        json={
            'actor': 'tester',
            'continuity_id': 'missing',
            'start_phrase': 'wrong',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 403
    assert response.json()['detail'] == (
        'Explicit certified successor-next-generation monitoring approval required'
    )


def test_audit_requires_existing_monitoring() -> None:
    response = client().post(
        '/auron/demo1/v21.370/health/audit',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION HEALTH',
            'observed_successor_next_generation_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'healthy',
        },
    )
    assert response.status_code == 404


def test_drift_open_requires_existing_monitoring() -> None:
    response = client().post(
        '/auron/demo1/v21.370/drift/open',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'drift_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION DRIFT',
            'trigger_audit_id': 'missing',
            'reason': 'test',
        },
    )
    assert response.status_code == 404


def test_drift_resolution_requires_existing_monitoring() -> None:
    response = client().post(
        '/auron/demo1/v21.370/drift/resolve',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION DRIFT',
            'corrected_successor_next_generation_hash': 'b' * 64,
            'control_state': 'healthy',
            'remediation_reference': 'REM-1',
            'remediation_statement': 'corrected',
        },
    )
    assert response.status_code == 404


def test_command_center_is_available() -> None:
    response = client().get('/auron/demo1/v21.370/command-center')
    assert response.status_code == 200
    assert 'v21.370' in response.text
