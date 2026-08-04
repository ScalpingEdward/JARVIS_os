from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_continuity_v21_418 import (
    reset_telegram_successor_next_generation_eleven_continuity_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_eleven_monitoring_v21_417 import (
    _baseline_store,
    _monitor_store,
    reset_telegram_successor_next_generation_eleven_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_eleven_continuity_store()
    reset_telegram_successor_next_generation_eleven_monitoring_store()


def seed_baseline() -> tuple[str, str]:
    monitoring_id = 'monitor-v21-417'
    baseline_id = 'baseline-v21-417'
    active_hash = 'a' * 64
    _monitor_store['cert-v21-416'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-eleven-renewed-baseline-active',
        'active_successor_next_generation_eleven_hash': active_hash,
        'immutable': True,
        'integrity_hash': 'b' * 64,
    }
    _baseline_store[monitoring_id] = {
        'baseline_id': baseline_id,
        'monitoring_id': monitoring_id,
        'baseline_state': 'successor-next-generation-eleven-renewed-baseline-certified-active',
        'active_successor_next_generation_eleven_hash': active_hash,
        'immutable': True,
        'integrity_hash': 'c' * 64,
    }
    return baseline_id, active_hash


def start_continuity(client: TestClient) -> dict:
    baseline_id, _ = seed_baseline()
    response = client.post('/auron/demo1/v21.418/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': baseline_id,
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN BASELINE CONTINUITY',
        'validity_days': 90,
        'checkpoint_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['continuity']


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.418/continuity/start' in paths
    assert '/auron/demo1/v21.418/continuity/checkpoint' in paths
    assert '/auron/demo1/v21.418/baseline/expire' in paths
    assert '/auron/demo1/v21.418/renewal/request' in paths
    assert '/auron/demo1/v21.418/status' in paths
    assert '/auron/demo1/v21.418/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.418/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuities': 0,
        'checkpoints': 0,
        'expiries': 0,
        'renewal_requests': 0,
        'external_calls_made': 0,
        'mode': 'successor-next-generation-eleven-renewed-baseline-continuity-expiry-renewal-governance',
    }


def test_start_requires_explicit_phrase() -> None:
    baseline_id, _ = seed_baseline()
    response = build_client().post('/auron/demo1/v21.418/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': baseline_id,
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_healthy_checkpoint_continuity() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.418/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN BASELINE CONTINUITY',
        'observed_successor_next_generation_eleven_hash': 'a' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Continuity healthy.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is True
    assert response.json()['continuity']['continuity_state'] == 'successor-next-generation-eleven-renewed-baseline-continuity-active'


def test_hash_mismatch_fails_closed() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.418/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN BASELINE CONTINUITY',
        'observed_successor_next_generation_eleven_hash': 'd' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Unexpected hash.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is False
    assert response.json()['continuity']['continuity_state'] == 'successor-next-generation-eleven-continuity-broken'


def test_expiry_to_renewal_request_flow() -> None:
    client = build_client()
    continuity = start_continuity(client)
    expired_at = (datetime.now(timezone.utc) + timedelta(days=91)).isoformat()
    expiry_response = client.post('/auron/demo1/v21.418/baseline/expire', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'expiry_phrase': 'EXPIRE AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN RENEWED BASELINE',
        'expiry_reference': 'EXP-418',
        'expiry_statement': 'Validity elapsed.',
        'expired_at': expired_at,
    })
    assert expiry_response.status_code == 200
    expiry = expiry_response.json()['expiry']
    renewal_response = client.post('/auron/demo1/v21.418/renewal/request', json={
        'actor': 'master-brano',
        'expiry_id': expiry['expiry_id'],
        'renewal_phrase': 'REQUEST AURON TELEGRAM SUCCESSOR NEXT GENERATION ELEVEN RENEWAL',
        'renewal_reference': 'REN-418',
        'renewal_statement': 'Request successor generation twelve.',
    })
    assert renewal_response.status_code == 200
    assert renewal_response.json()['renewal_request']['renewal_state'] == 'successor-next-generation-eleven-renewal-requested'
    assert renewal_response.json()['next_layer'] == 'successor-next-generation-twelve-restoration-and-succession'


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.418/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION ELEVEN CONTINUITY COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
