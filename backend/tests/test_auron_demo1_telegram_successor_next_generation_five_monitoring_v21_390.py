from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_five_monitoring_v21_390 import (
    reset_telegram_successor_next_generation_five_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_five_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.390/monitoring/start' in paths
    assert '/auron/demo1/v21.390/health/audit' in paths
    assert '/auron/demo1/v21.390/drift/open' in paths
    assert '/auron/demo1/v21.390/drift/resolve' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.390/status')
    assert response.status_code == 200
    body = response.json()
    assert body['monitoring_records'] == 0
    assert body['health_audits'] == 0
    assert body['drifts'] == 0
    assert body['resolutions'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_monitoring_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.390/monitoring/start',
        json={
            'actor': 'tester',
            'stabilization_id': 'missing',
            'start_phrase': 'WRONG',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 403


def test_missing_monitoring_blocks_audit() -> None:
    response = client().post(
        '/auron/demo1/v21.390/health/audit',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE HEALTH',
            'observed_successor_next_generation_five_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'check',
        },
    )
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_open() -> None:
    response = client().post(
        '/auron/demo1/v21.390/drift/open',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_id': 'missing',
            'open_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE DRIFT',
            'drift_reason': 'hash mismatch',
        },
    )
    assert response.status_code == 404


def test_missing_drift_blocks_resolution() -> None:
    response = client().post(
        '/auron/demo1/v21.390/drift/resolve',
        json={
            'actor': 'tester',
            'drift_id': 'missing',
            'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE DRIFT',
            'corrected_successor_next_generation_five_hash': 'b' * 64,
            'control_state': 'healthy',
            'remediation_reference': 'REF-1',
            'resolution_statement': 'resolved',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.390/command-center')
    assert response.status_code == 200
    assert 'CERTIFIED SUCCESSOR NEXT GENERATION FIVE MONITORING' in response.text
    assert 'no outbound message' in response.text
