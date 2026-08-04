from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_six_continuity_v21_397 import (
    reset_telegram_renewed_successor_next_generation_six_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_successor_next_generation_six_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.397/continuity/start' in paths
    assert '/auron/demo1/v21.397/recertification/health-check' in paths
    assert '/auron/demo1/v21.397/baseline/expire' in paths
    assert '/auron/demo1/v21.397/baseline/validity/renew' in paths
    assert '/auron/demo1/v21.397/status' in paths
    assert '/auron/demo1/v21.397/command-center' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.397/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuities': 0,
        'health_checks': 0,
        'expiries': 0,
        'validity_renewals': 0,
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-six-continuity-health-expiry-governance',
    }


def test_explicit_continuity_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.397/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'baseline-missing',
        'start_phrase': 'wrong',
        'health_check_interval_days': 30,
        'validity_days': 365,
    })
    assert response.status_code == 403


def test_v21_396_baseline_required() -> None:
    response = client().post('/auron/demo1/v21.397/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'baseline-missing',
        'start_phrase': 'START AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX CONTINUITY',
        'health_check_interval_days': 30,
        'validity_days': 365,
    })
    assert response.status_code == 409


def test_missing_continuity_blocks_health_check() -> None:
    response = client().post('/auron/demo1/v21.397/recertification/health-check', json={
        'actor': 'tester',
        'continuity_id': 'continuity-missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX RECERTIFICATION HEALTH',
        'observed_renewed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'statement': 'healthy',
    })
    assert response.status_code == 404


def test_missing_continuity_blocks_expiry() -> None:
    response = client().post('/auron/demo1/v21.397/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'continuity-missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION SIX BASELINE',
        'expiry_reference': 'EXP-1',
        'expiry_statement': 'expired',
    })
    assert response.status_code == 404


def test_missing_continuity_blocks_validity_renewal() -> None:
    response = client().post('/auron/demo1/v21.397/baseline/validity/renew', json={
        'actor': 'tester',
        'continuity_id': 'continuity-missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION SIX BASELINE VALIDITY',
        'observed_renewed_baseline_hash': 'b' * 64,
        'control_state': 'healthy',
        'validity_days': 365,
        'renewal_reference': 'REN-1',
    })
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.397/command-center')
    assert response.status_code == 200
    assert 'RENEWED SUCCESSOR NEXT GENERATION SIX CONTINUITY' in response.text
    assert 'no outbound message' in response.text
