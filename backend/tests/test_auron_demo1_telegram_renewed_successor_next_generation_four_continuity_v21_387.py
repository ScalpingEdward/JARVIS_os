from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_four_continuity_v21_387 import (
    reset_telegram_renewed_successor_next_generation_four_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_successor_next_generation_four_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.387/continuity/start' in paths
    assert '/auron/demo1/v21.387/health/check' in paths
    assert '/auron/demo1/v21.387/baseline/expire' in paths
    assert '/auron/demo1/v21.387/baseline/renew-validity' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.387/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuity_records': 0,
        'health_checks': 0,
        'baseline_expiries': 0,
        'validity_renewals': 0,
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-four-continuity-health-expiry-governance',
    }


def test_explicit_continuity_phrase_enforcement() -> None:
    response = client().post('/auron/demo1/v21.387/continuity/start', json={
        'actor': 'tester',
        'monitoring_id': 'missing',
        'start_phrase': 'WRONG',
    })
    assert response.status_code == 403


def test_missing_continuity_health_check_blocking() -> None:
    response = client().post('/auron/demo1/v21.387/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR RECERTIFICATION HEALTH',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'statement': 'safe isolated check',
    })
    assert response.status_code == 404


def test_missing_continuity_expiry_blocking() -> None:
    response = client().post('/auron/demo1/v21.387/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION FOUR BASELINE',
        'reason': 'safe isolated expiry test',
    })
    assert response.status_code == 404


def test_missing_continuity_validity_renewal_blocking() -> None:
    response = client().post('/auron/demo1/v21.387/baseline/renew-validity', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION FOUR BASELINE VALIDITY',
        'renewal_reference': 'TEST-387',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.387/command-center')
    assert response.status_code == 200
    assert 'RENEWED SUCCESSOR NEXT GENERATION FOUR CONTINUITY' in response.text
    assert 'no outbound message' in response.text
