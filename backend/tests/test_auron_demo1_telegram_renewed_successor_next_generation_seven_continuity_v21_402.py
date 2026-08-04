from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_seven_continuity_v21_402 import (
    reset_telegram_renewed_successor_next_generation_seven_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_successor_next_generation_seven_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.402/continuity/start' in paths
    assert '/auron/demo1/v21.402/health/check' in paths
    assert '/auron/demo1/v21.402/baseline/expire' in paths
    assert '/auron/demo1/v21.402/baseline/validity/renew' in paths
    assert '/auron/demo1/v21.402/status' in paths
    assert '/auron/demo1/v21.402/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.402/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuities': 0,
        'health_checks': 0,
        'expiries': 0,
        'validity_renewals': 0,
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-seven-continuity-health-expiry-governance',
    }


def test_explicit_continuity_phrase_enforcement() -> None:
    response = client().post('/auron/demo1/v21.402/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'missing',
        'start_phrase': 'wrong',
        'health_check_interval_days': 30,
    })
    assert response.status_code == 403


def test_v21_401_baseline_required() -> None:
    response = client().post('/auron/demo1/v21.402/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'missing',
        'start_phrase': 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN CONTINUITY',
        'health_check_interval_days': 30,
    })
    assert response.status_code == 409


def test_continuity_required_before_health_check() -> None:
    response = client().post('/auron/demo1/v21.402/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN RECERTIFICATION HEALTH',
        'observed_successor_next_generation_seven_hash': 'a' * 64,
        'control_state': 'healthy',
        'health_statement': 'healthy',
    })
    assert response.status_code == 404


def test_continuity_required_before_expiry() -> None:
    response = client().post('/auron/demo1/v21.402/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SEVEN BASELINE',
        'expiry_reference': 'EXP-1',
        'expiry_statement': 'expired',
    })
    assert response.status_code == 404


def test_continuity_required_before_validity_renewal() -> None:
    response = client().post('/auron/demo1/v21.402/baseline/validity/renew', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SEVEN BASELINE VALIDITY',
        'observed_successor_next_generation_seven_hash': 'b' * 64,
        'control_state': 'healthy',
        'validity_extension_days': 365,
        'renewal_reference': 'REN-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.402/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION SEVEN CONTINUITY' in response.text
    assert 'no outbound message' in response.text
