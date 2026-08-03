from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_renewed_successor_next_generation_continuity_v21_372 as module


def client() -> TestClient:
    app = FastAPI()
    app.include_router(module.router)
    module.reset_telegram_renewed_successor_next_generation_continuity_store()
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in module.router.routes}
    assert '/auron/demo1/v21.372/continuity/start' in paths
    assert '/auron/demo1/v21.372/health/check' in paths
    assert '/auron/demo1/v21.372/baseline/expire' in paths
    assert '/auron/demo1/v21.372/baseline/validity/renew' in paths
    assert '/auron/demo1/v21.372/status' in paths
    assert '/auron/demo1/v21.372/command-center' in paths


def test_status_is_safe_and_empty() -> None:
    response = client().get('/auron/demo1/v21.372/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuity_monitors': 0,
        'health_checks': 0,
        'expired_baselines': 0,
        'validity_renewals': 0,
        'external_calls_made': 0,
        'mode': 'renewed-successor-next-generation-continuity-health-check-baseline-expiry-governance',
    }


def test_start_requires_explicit_phrase() -> None:
    response = client().post(
        '/auron/demo1/v21.372/continuity/start',
        json={
            'actor': 'tester',
            'monitoring_id': 'missing',
            'start_phrase': 'wrong',
            'health_check_interval_days': 30,
            'validity_days': 365,
        },
    )
    assert response.status_code == 403


def test_health_check_requires_existing_continuity() -> None:
    response = client().post(
        '/auron/demo1/v21.372/health/check',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION RECERTIFICATION HEALTH',
            'observed_baseline_hash': 'a' * 64,
            'control_state': 'healthy',
            'statement': 'healthy',
        },
    )
    assert response.status_code == 404


def test_expiry_requires_existing_continuity() -> None:
    response = client().post(
        '/auron/demo1/v21.372/baseline/expire',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED SUCCESSOR NEXT GENERATION BASELINE',
            'expiry_reference': 'ref',
            'expiry_statement': 'expired',
        },
    )
    assert response.status_code == 404


def test_validity_renewal_requires_existing_continuity() -> None:
    response = client().post(
        '/auron/demo1/v21.372/baseline/validity/renew',
        json={
            'actor': 'tester',
            'continuity_monitor_id': 'missing',
            'renewal_phrase': 'RENEW AURON TELEGRAM SUCCESSOR NEXT GENERATION BASELINE VALIDITY',
            'observed_baseline_hash': 'b' * 64,
            'control_state': 'healthy',
            'extension_days': 365,
            'renewal_reference': 'ref',
        },
    )
    assert response.status_code == 404


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.372/command-center')
    assert response.status_code == 200
    assert 'v21.372' in response.text
    assert 'RENEWED SUCCESSOR NEXT GENERATION CONTINUITY' in response.text
