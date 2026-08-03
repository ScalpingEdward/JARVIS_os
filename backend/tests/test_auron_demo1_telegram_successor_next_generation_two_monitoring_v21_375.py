from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_two_monitoring_v21_375 import (
    reset_telegram_successor_next_generation_two_monitoring_store,
    router,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_two_monitoring_store()


def test_router_registration() -> None:
    client = _client()
    response = client.get('/auron/demo1/v21.375/status')
    assert response.status_code == 200


def test_safe_empty_status() -> None:
    response = _client().get('/auron/demo1/v21.375/status')
    assert response.json() == {
        'monitoring_records': 0,
        'health_audits': 0,
        'drift_records': 0,
        'drift_resolutions': 0,
        'open_drifts': 0,
        'external_calls_made': 0,
        'mode': 'certified-successor-next-generation-two-monitoring-health-audit-drift-governance',
    }


def test_explicit_monitoring_phrase_enforced() -> None:
    response = _client().post(
        '/auron/demo1/v21.375/monitoring/start',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'start_phrase': 'WRONG',
            'audit_interval_days': 30,
        },
    )
    assert response.status_code == 403


def test_missing_monitoring_blocks_audit() -> None:
    response = _client().post(
        '/auron/demo1/v21.375/health/audit',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'audit_phrase': 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO HEALTH',
            'observed_successor_next_generation_two_hash': 'a' * 64,
            'continuity_state': 'healthy',
            'statement': 'check',
        },
    )
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_opening() -> None:
    response = _client().post(
        '/auron/demo1/v21.375/drift/open',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'drift_phrase': 'OPEN AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO DRIFT',
            'trigger_audit_id': 'missing-audit',
            'reason': 'test',
        },
    )
    assert response.status_code == 404


def test_missing_monitoring_blocks_drift_resolution() -> None:
    response = _client().post(
        '/auron/demo1/v21.375/drift/resolve',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'resolution_phrase': 'RESOLVE AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO DRIFT',
            'corrected_successor_next_generation_two_hash': 'b' * 64,
            'control_state': 'healthy',
            'remediation_reference': 'ref',
            'remediation_statement': 'fixed',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = _client().get('/auron/demo1/v21.375/command-center')
    assert response.status_code == 200
    assert 'CERTIFIED SUCCESSOR NEXT GENERATION TWO MONITORING' in response.text
    assert 'no Telegram API call' in response.text
