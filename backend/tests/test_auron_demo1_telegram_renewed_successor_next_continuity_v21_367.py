from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_continuity_v21_367 import (
    reset_telegram_renewed_successor_next_continuity_store,
    router,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def setup_function() -> None:
    reset_telegram_renewed_successor_next_continuity_store()


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.367/status' in paths
    assert '/auron/demo1/v21.367/continuity/start' in paths
    assert '/auron/demo1/v21.367/health/check' in paths
    assert '/auron/demo1/v21.367/baseline/expire' in paths
    assert '/auron/demo1/v21.367/baseline/validity/renew' in paths


def test_safe_empty_status() -> None:
    response = client.get('/auron/demo1/v21.367/status')
    assert response.status_code == 200
    body = response.json()
    assert body['continuity_records'] == 0
    assert body['recertification_health_checks'] == 0
    assert body['expired_baselines'] == 0
    assert body['external_calls_made'] == 0


def test_explicit_start_phrase_enforced() -> None:
    response = client.post('/auron/demo1/v21.367/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'missing',
        'start_phrase': 'WRONG',
        'health_interval_days': 30,
        'validity_days': 365,
    })
    assert response.status_code == 403


def test_missing_continuity_blocks_health_check() -> None:
    response = client.post('/auron/demo1/v21.367/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT RECERTIFICATION HEALTH',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'statement': 'healthy',
    })
    assert response.status_code == 404


def test_missing_continuity_blocks_expiry() -> None:
    response = client.post('/auron/demo1/v21.367/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT BASELINE',
        'reason': 'expired',
    })
    assert response.status_code == 404


def test_missing_expiry_blocks_validity_renewal() -> None:
    response = client.post('/auron/demo1/v21.367/baseline/validity/renew', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT BASELINE VALIDITY',
        'renewal_reference': 'ref',
        'validity_days': 365,
    })
    assert response.status_code == 404
