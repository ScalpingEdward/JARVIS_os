from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_renewed_successor_next_generation_five_continuity_v21_392 import (
    reset_telegram_renewed_successor_next_generation_five_continuity_store,
    router,
)


def client() -> TestClient:
    reset_telegram_renewed_successor_next_generation_five_continuity_store()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_route_registration() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.392/continuity/start' in paths
    assert '/auron/demo1/v21.392/health/check' in paths
    assert '/auron/demo1/v21.392/baseline/expire' in paths
    assert '/auron/demo1/v21.392/baseline/renew-validity' in paths


def test_safe_empty_status() -> None:
    response = client().get('/auron/demo1/v21.392/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuity_records': 0,
        'health_checks': 0,
        'baseline_expiries': 0,
        'validity_renewals': 0,
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-five-continuity-health-expiry-governance',
    }


def test_explicit_continuity_phrase_enforcement() -> None:
    response = client().post(
        '/auron/demo1/v21.392/continuity/start',
        json={'actor': 'tester', 'monitoring_id': 'missing', 'start_phrase': 'WRONG'},
    )
    assert response.status_code == 403


def test_missing_continuity_health_check_blocking() -> None:
    response = client().post(
        '/auron/demo1/v21.392/health/check',
        json={
            'actor': 'tester',
            'continuity_id': 'missing',
            'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE RECERTIFICATION HEALTH',
            'observed_baseline_hash': 'a' * 64,
            'control_state': 'healthy',
            'statement': 'healthy',
        },
    )
    assert response.status_code == 404


def test_missing_continuity_expiry_blocking() -> None:
    response = client().post(
        '/auron/demo1/v21.392/baseline/expire',
        json={
            'actor': 'tester',
            'continuity_id': 'missing',
            'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION FIVE BASELINE',
            'reason': 'expired',
        },
    )
    assert response.status_code == 404


def test_missing_continuity_validity_renewal_blocking() -> None:
    response = client().post(
        '/auron/demo1/v21.392/baseline/renew-validity',
        json={
            'actor': 'tester',
            'continuity_id': 'missing',
            'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION FIVE BASELINE VALIDITY',
            'renewal_reference': 'REF-1',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.392/command-center')
    assert response.status_code == 200
    assert 'RENEWED SUCCESSOR NEXT GENERATION FIVE CONTINUITY' in response.text
    assert 'no outbound message' in response.text
