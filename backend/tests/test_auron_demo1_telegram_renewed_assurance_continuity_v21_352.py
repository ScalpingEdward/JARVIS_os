from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_assurance_continuity_v21_352 import (
    reset_telegram_renewed_assurance_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_assurance_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.352/continuity/start' in paths
    assert '/auron/demo1/v21.352/health/check' in paths
    assert '/auron/demo1/v21.352/baseline/expire' in paths
    assert '/auron/demo1/v21.352/baseline/expiry-window/renew' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.352/status')
    assert response.status_code == 200
    assert response.json()['continuity_records'] == 0
    assert response.json()['external_calls_made'] == 0


def test_explicit_start_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.352/continuity/start', json={
        'actor': 'tester',
        'baseline_id': 'missing',
        'start_phrase': 'WRONG',
        'health_check_interval_days': 30,
        'baseline_validity_days': 365,
    })
    assert response.status_code == 403


def test_missing_continuity_blocks_health_check() -> None:
    response = client().post('/auron/demo1/v21.352/health/check', json={
        'actor': 'tester',
        'continuity_id': 'missing',
        'check_phrase': 'CHECK AURON TELEGRAM RECERTIFICATION HEALTH',
        'observed_baseline_hash': 'a' * 64,
        'control_state': 'healthy',
        'check_statement': 'healthy',
    })
    assert response.status_code == 404
