from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_twelve_continuity_v21_421 import (
    _CHECK_PHRASE,
    _EXPIRE_PHRASE,
    _RENEWAL_PHRASE,
    _START_PHRASE,
    _continuity_store,
    _expiry_store,
    _renewal_store,
    reset_telegram_successor_next_generation_twelve_continuity_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_twelve_monitoring_v21_420 import (
    _baseline_store,
    _monitor_store,
)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_twelve_continuity_store()
    _baseline_store.clear()
    _monitor_store.clear()


def seed() -> tuple[str, str, str]:
    monitoring_id = 'monitor-12'
    baseline_id = 'baseline-12'
    active_hash = 'a' * 64
    _monitor_store['cert-12'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'successor-next-generation-twelve-renewed-baseline-active',
        'active_successor_next_generation_twelve_hash': active_hash,
        'integrity_hash': 'monitor-integrity',
        'immutable': True,
    }
    _baseline_store[monitoring_id] = {
        'baseline_id': baseline_id,
        'monitoring_id': monitoring_id,
        'baseline_state': 'successor-next-generation-twelve-renewed-baseline-certified-active',
        'active_successor_next_generation_twelve_hash': active_hash,
        'integrity_hash': 'baseline-integrity',
        'immutable': True,
    }
    return monitoring_id, baseline_id, active_hash


def start(c: TestClient, baseline_id: str) -> dict:
    response = c.post('/auron/demo1/v21.421/continuity/start', json={
        'actor': 'tester',
        'baseline_id': baseline_id,
        'start_phrase': _START_PHRASE,
        'validity_days': 90,
        'checkpoint_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['continuity']


def test_router_and_empty_status() -> None:
    c = client()
    response = c.get('/auron/demo1/v21.421/status')
    assert response.status_code == 200
    assert response.json()['continuities'] == 0
    assert response.json()['external_calls_made'] == 0


def test_start_requires_explicit_phrase() -> None:
    _, baseline_id, _ = seed()
    response = client().post('/auron/demo1/v21.421/continuity/start', json={
        'actor': 'tester', 'baseline_id': baseline_id, 'start_phrase': 'NO'
    })
    assert response.status_code == 403


def test_healthy_checkpoint_continuity() -> None:
    _, baseline_id, active_hash = seed()
    c = client()
    continuity = start(c, baseline_id)
    response = c.post('/auron/demo1/v21.421/continuity/checkpoint', json={
        'actor': 'tester',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': _CHECK_PHRASE,
        'observed_successor_next_generation_twelve_hash': active_hash,
        'control_state': 'healthy',
        'continuity_statement': 'all controls healthy',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is True
    assert response.json()['external_calls_made'] == 0


def test_hash_mismatch_fails_closed() -> None:
    _, baseline_id, _ = seed()
    c = client()
    continuity = start(c, baseline_id)
    response = c.post('/auron/demo1/v21.421/continuity/checkpoint', json={
        'actor': 'tester',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': _CHECK_PHRASE,
        'observed_successor_next_generation_twelve_hash': 'b' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'hash mismatch',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is False
    assert response.json()['continuity']['continuity_state'] == 'successor-next-generation-twelve-continuity-broken'


def test_expiry_to_renewal_flow() -> None:
    monitoring_id, baseline_id, _ = seed()
    c = client()
    continuity = start(c, baseline_id)
    expired_at = (datetime.now(timezone.utc) + timedelta(days=91)).isoformat()
    expiry_response = c.post('/auron/demo1/v21.421/baseline/expire', json={
        'actor': 'tester',
        'continuity_id': continuity['continuity_id'],
        'expiry_phrase': _EXPIRE_PHRASE,
        'expiry_reference': 'expiry-12',
        'expiry_statement': 'validity elapsed',
        'expired_at': expired_at,
    })
    assert expiry_response.status_code == 200
    expiry = expiry_response.json()['expiry']
    assert _monitor_store['cert-12']['monitoring_state'] == 'successor-next-generation-twelve-renewal-required'
    renewal_response = c.post('/auron/demo1/v21.421/renewal/request', json={
        'actor': 'tester',
        'expiry_id': expiry['expiry_id'],
        'renewal_phrase': _RENEWAL_PHRASE,
        'renewal_reference': 'renewal-12',
        'renewal_statement': 'request generation thirteen',
    })
    assert renewal_response.status_code == 200
    assert renewal_response.json()['renewal_request']['renewal_state'] == 'successor-next-generation-twelve-renewal-requested'
    assert len(_expiry_store) == 1
    assert len(_renewal_store) == 1
    assert monitoring_id == expiry['monitoring_id']


def test_command_center_available() -> None:
    response = client().get('/auron/demo1/v21.421/command-center')
    assert response.status_code == 200
    assert 'AURON v21.421' in response.text
    assert 'no Telegram API call' in response.text
