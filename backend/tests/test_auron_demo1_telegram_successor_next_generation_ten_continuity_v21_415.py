from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_continuity_v21_415 import (
    reset_telegram_successor_next_generation_ten_continuity_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_ten_monitoring_v21_414 import (
    _baseline_store,
    _monitor_store,
    reset_telegram_successor_next_generation_ten_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_ten_continuity_store()
    reset_telegram_successor_next_generation_ten_monitoring_store()


def seed_baseline() -> str:
    monitoring_id = 'monitor-v21-414'
    baseline_id = 'baseline-v21-414'
    _monitor_store['cert-v21-413'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-ten-renewed-baseline-active',
        'active_successor_next_generation_ten_hash': 'a' * 64,
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    _baseline_store[monitoring_id] = {
        'baseline_id': baseline_id,
        'monitoring_id': monitoring_id,
        'baseline_state': 'successor-next-generation-ten-renewed-baseline-certified-active',
        'active_successor_next_generation_ten_hash': 'a' * 64,
        'integrity_hash': 'c' * 64,
        'immutable': True,
    }
    return baseline_id


def start_continuity(client: TestClient) -> dict:
    response = client.post('/auron/demo1/v21.415/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': seed_baseline(),
        'start_phrase': 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN BASELINE CONTINUITY',
        'validity_days': 90,
        'checkpoint_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['continuity']


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.415/continuity/start' in paths
    assert '/auron/demo1/v21.415/continuity/checkpoint' in paths
    assert '/auron/demo1/v21.415/baseline/expire' in paths
    assert '/auron/demo1/v21.415/renewal/request' in paths
    assert '/auron/demo1/v21.415/status' in paths
    assert '/auron/demo1/v21.415/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.415/status')
    assert response.status_code == 200
    assert response.json()['external_calls_made'] == 0
    assert response.json()['continuities'] == 0


def test_start_requires_explicit_phrase() -> None:
    response = build_client().post('/auron/demo1/v21.415/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': seed_baseline(),
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_healthy_checkpoint_preserves_continuity() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.415/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN BASELINE CONTINUITY',
        'observed_successor_next_generation_ten_hash': 'a' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Continuity remains stable.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is True
    assert response.json()['continuity']['continuity_state'] == 'successor-next-generation-ten-renewed-baseline-continuity-active'


def test_hash_mismatch_fails_closed() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.415/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN BASELINE CONTINUITY',
        'observed_successor_next_generation_ten_hash': 'd' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Hash mismatch detected.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is False
    assert response.json()['continuity']['continuity_state'] == 'successor-next-generation-ten-continuity-broken'


def test_expiry_and_renewal_flow() -> None:
    client = build_client()
    continuity = start_continuity(client)
    expired_at = (datetime.now(timezone.utc) + timedelta(days=91)).isoformat()
    expiry_response = client.post('/auron/demo1/v21.415/baseline/expire', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'expiry_phrase': 'EXPIRE AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN RENEWED BASELINE',
        'expiry_reference': 'EXP-415',
        'expiry_statement': 'Validity elapsed.',
        'expired_at': expired_at,
    })
    assert expiry_response.status_code == 200
    expiry = expiry_response.json()['expiry']
    renewal_response = client.post('/auron/demo1/v21.415/renewal/request', json={
        'actor': 'master-brano',
        'expiry_id': expiry['expiry_id'],
        'renewal_phrase': 'REQUEST AURON TELEGRAM SUCCESSOR NEXT GENERATION TEN RENEWAL',
        'renewal_reference': 'REN-415',
        'renewal_statement': 'Request controlled successor renewal.',
    })
    assert renewal_response.status_code == 200
    assert renewal_response.json()['renewal_request']['renewal_state'] == 'successor-next-generation-ten-renewal-requested'
    assert renewal_response.json()['external_calls_made'] == 0


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.415/command-center')
    assert response.status_code == 200
    assert 'SUCCESSOR NEXT GENERATION TEN CONTINUITY COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
