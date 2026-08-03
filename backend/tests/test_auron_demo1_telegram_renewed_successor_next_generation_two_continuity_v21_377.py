from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_two_continuity_v21_377 import (
    reset_telegram_renewed_successor_next_generation_two_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_successor_next_generation_two_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.377/continuity/start' in paths
    assert '/auron/demo1/v21.377/health/check' in paths
    assert '/auron/demo1/v21.377/baseline/expire' in paths
    assert '/auron/demo1/v21.377/baseline/validity/renew' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.377/status')
    assert response.status_code == 200
    assert response.json()['continuity_records'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_continuity_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.377/continuity/start', json={
        'actor': 'tester',
        'monitoring_id': 'missing-monitoring',
        'start_phrase': 'WRONG',
    })
    assert response.status_code == 403


def test_missing_continuity_health_check_blocked() -> None:
    response = client().post('/auron/demo1/v21.377/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO RECERTIFICATION HEALTH',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'statement': 'check',
    })
    assert response.status_code == 404


def test_missing_continuity_expiry_blocked() -> None:
    response = client().post('/auron/demo1/v21.377/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION TWO BASELINE',
        'expiry_reference': 'ref',
        'expiry_statement': 'expired',
    })
    assert response.status_code == 404


def test_missing_continuity_validity_renewal_blocked() -> None:
    response = client().post('/auron/demo1/v21.377/baseline/validity/renew', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION TWO BASELINE VALIDITY',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'renewal_reference': 'ref',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.377/command-center')
    assert response.status_code == 200
    assert 'RENEWED SUCCESSOR NEXT GENERATION TWO CONTINUITY' in response.text
    assert 'no Telegram API call' in response.text
