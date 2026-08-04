from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_three_continuity_v21_382 import (
    reset_telegram_renewed_successor_next_generation_three_continuity_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_renewed_successor_next_generation_three_continuity_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.382/continuity/start' in paths
    assert '/auron/demo1/v21.382/health/check' in paths
    assert '/auron/demo1/v21.382/baseline/expire' in paths
    assert '/auron/demo1/v21.382/baseline/renew-validity' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.382/status')
    assert response.status_code == 200
    body = response.json()
    assert body['continuity_records'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_continuity_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.382/continuity/start', json={
        'actor': 'tester',
        'monitoring_id': 'monitoring-1',
        'start_phrase': 'WRONG',
    })
    assert response.status_code == 403


def test_missing_continuity_health_check_blocked() -> None:
    response = client.post('/auron/demo1/v21.382/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE RECERTIFICATION HEALTH',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'statement': 'check',
    })
    assert response.status_code == 404


def test_missing_continuity_expiry_blocked() -> None:
    response = client.post('/auron/demo1/v21.382/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION THREE BASELINE',
        'reason': 'expired',
    })
    assert response.status_code == 404


def test_missing_continuity_validity_renewal_blocked() -> None:
    response = client.post('/auron/demo1/v21.382/baseline/renew-validity', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION THREE BASELINE VALIDITY',
        'extension_days': 30,
        'renewal_reference': 'ref-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client.get('/auron/demo1/v21.382/command-center')
    assert response.status_code == 200
    assert 'RENEWED SUCCESSOR NEXT GENERATION THREE CONTINUITY' in response.text
