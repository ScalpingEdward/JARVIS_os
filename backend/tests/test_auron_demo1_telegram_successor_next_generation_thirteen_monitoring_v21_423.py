from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_thirteen_monitoring_v21_423 import router, status


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.423/monitoring/start' in paths
    assert '/auron/demo1/v21.423/health/audit' in paths
    assert '/auron/demo1/v21.423/drift/open' in paths
    assert '/auron/demo1/v21.423/baseline/certify' in paths
    assert '/auron/demo1/v21.423/status' in paths
    assert '/auron/demo1/v21.423/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['monitorings'] == 0
    assert result['drifts'] == 0


def test_explicit_monitoring_phrase_required() -> None:
    response = client().post('/auron/demo1/v21.423/monitoring/start', json={
        'actor': 'tester',
        'certification_id': 'missing',
        'start_phrase': 'wrong phrase',
        'audit_interval_days': 30,
    })
    assert response.status_code == 403


def test_explicit_audit_phrase_required() -> None:
    response = client().post('/auron/demo1/v21.423/health/audit', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'audit_phrase': 'wrong phrase',
        'observed_successor_next_generation_thirteen_hash': 'a' * 64,
        'control_state': 'healthy',
        'audit_statement': 'test',
    })
    assert response.status_code == 403


def test_explicit_drift_phrase_required() -> None:
    response = client().post('/auron/demo1/v21.423/drift/open', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'trigger_audit_id': 'missing',
        'open_phrase': 'wrong phrase',
        'drift_reference': 'test',
        'drift_statement': 'test',
    })
    assert response.status_code == 403


def test_explicit_baseline_phrase_required() -> None:
    response = client().post('/auron/demo1/v21.423/baseline/certify', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'certification_phrase': 'wrong phrase',
        'observed_successor_next_generation_thirteen_hash': 'a' * 64,
        'control_state': 'healthy',
        'baseline_reference': 'test',
        'baseline_statement': 'test',
    })
    assert response.status_code == 403


def test_command_center_safe_mode() -> None:
    response = client().get('/auron/demo1/v21.423/command-center')
    assert response.status_code == 200
    assert 'no Telegram API call' in response.text
    assert 'no outbound message' in response.text
