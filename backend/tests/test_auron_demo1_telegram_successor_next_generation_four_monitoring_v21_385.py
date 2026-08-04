from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_four_monitoring_v21_385 import (
    reset_telegram_successor_next_generation_four_monitoring_store,
    router,
)


def client() -> TestClient:
    reset_telegram_successor_next_generation_four_monitoring_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.385/monitoring/start' in paths
    assert '/auron/demo1/v21.385/health/audit' in paths
    assert '/auron/demo1/v21.385/drift/open' in paths
    assert '/auron/demo1/v21.385/drift/resolve' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.385/status')
    assert response.status_code == 200
    body = response.json()
    assert body['monitoring_records'] == 0
    assert body['health_audits'] == 0
    assert body['open_drifts'] == 0
    assert body['drift_resolutions'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_monitoring_phrase_enforced() -> None:
    response = client().post(
        '/auron/demo1/v21.385/monitoring/start',
        json={
            'actor': 'tester',
            'continuity_id': 'continuity-1',
            'start_phrase': 'NO',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 403


def test_missing_monitoring_blocks_audit() -> None:
    response = client().post(
        '/auron/demo1/v21.385/health/audit',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR HEALTH',
            'observed_successor_next_generation_four_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'check',
        },
    )
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_open() -> None:
    response = client().post(
        '/auron/demo1/v21.385/drift/open',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'drift_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR DRIFT',
            'trigger_audit_id': 'audit-1',
            'reason': 'test',
        },
    )
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_resolution() -> None:
    response = client().post(
        '/auron/demo1/v21.385/drift/resolve',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR DRIFT',
            'corrected_successor_next_generation_four_hash': 'b' * 64,
            'control_state': 'healthy',
            'remediation_reference': 'ref',
            'remediation_statement': 'fixed',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.385/command-center')
    assert response.status_code == 200
    assert 'CERTIFIED SUCCESSOR NEXT GENERATION FOUR MONITORING' in response.text
    assert 'no outbound message' in response.text
