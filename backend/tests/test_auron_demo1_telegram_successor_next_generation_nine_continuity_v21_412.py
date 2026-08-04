from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_continuity_v21_412 import (
    reset_telegram_successor_next_generation_nine_continuity_store,
    router,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_recertification_v21_411 import (
    _renewed_baseline_store,
    reset_telegram_successor_next_generation_nine_recertification_store,
)
from app.api.routes.auron_demo1_telegram_successor_next_generation_nine_monitoring_v21_410 import (
    _monitoring_store,
    reset_telegram_successor_next_generation_nine_monitoring_store,
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def setup_function() -> None:
    reset_telegram_successor_next_generation_nine_continuity_store()
    reset_telegram_successor_next_generation_nine_recertification_store()
    reset_telegram_successor_next_generation_nine_monitoring_store()


def seed_baseline() -> str:
    monitoring_id = 'monitoring-v21-412'
    baseline_id = 'baseline-v21-412'
    _monitoring_store['cert-v21-409'] = {
        'monitoring_id': monitoring_id,
        'monitoring_state': 'certified-successor-next-generation-nine-monitoring-active',
        'active_successor_next_generation_nine_hash': 'a' * 64,
    }
    _renewed_baseline_store['recertification-v21-411'] = {
        'baseline_id': baseline_id,
        'monitoring_id': monitoring_id,
        'baseline_state': 'successor-next-generation-nine-renewed-baseline-active',
        'active_successor_next_generation_nine_hash': 'a' * 64,
        'integrity_hash': 'b' * 64,
        'immutable': True,
    }
    return baseline_id


def start_continuity(client: TestClient, validity_days: int = 90) -> dict:
    baseline_id = seed_baseline()
    response = client.post('/auron/demo1/v21.412/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': baseline_id,
        'start_phrase': 'START AURON TELEGRAM RENEWED BASELINE CONTINUITY',
        'validity_days': validity_days,
        'checkpoint_interval_days': 30,
    })
    assert response.status_code == 200
    return response.json()['continuity']


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.412/continuity/start' in paths
    assert '/auron/demo1/v21.412/continuity/checkpoint' in paths
    assert '/auron/demo1/v21.412/baseline/expire' in paths
    assert '/auron/demo1/v21.412/renewal/request' in paths
    assert '/auron/demo1/v21.412/status' in paths
    assert '/auron/demo1/v21.412/command-center' in paths


def test_safe_empty_status() -> None:
    response = build_client().get('/auron/demo1/v21.412/status')
    assert response.status_code == 200
    assert response.json() == {
        'continuities': 0,
        'checkpoints': 0,
        'expiries': 0,
        'renewal_requests': 0,
        'external_calls_made': 0,
        'mode': 'renewed-baseline-monitoring-continuity-expiry-governance',
    }


def test_start_requires_explicit_phrase() -> None:
    baseline_id = seed_baseline()
    response = build_client().post('/auron/demo1/v21.412/continuity/start', json={
        'actor': 'master-brano',
        'baseline_id': baseline_id,
        'start_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_healthy_checkpoint_preserves_continuity() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.412/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM RENEWED BASELINE CONTINUITY',
        'observed_successor_next_generation_nine_hash': 'a' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Continuity remains stable.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is True
    assert response.json()['continuity']['continuity_state'] == 'renewed-baseline-continuity-active'
    assert response.json()['external_calls_made'] == 0


def test_hash_mismatch_fails_closed() -> None:
    client = build_client()
    continuity = start_continuity(client)
    response = client.post('/auron/demo1/v21.412/continuity/checkpoint', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'check_phrase': 'CHECK AURON TELEGRAM RENEWED BASELINE CONTINUITY',
        'observed_successor_next_generation_nine_hash': 'c' * 64,
        'control_state': 'healthy',
        'continuity_statement': 'Hash mismatch detected.',
    })
    assert response.status_code == 200
    assert response.json()['checkpoint']['healthy'] is False
    assert response.json()['continuity']['continuity_state'] == 'renewed-baseline-continuity-broken'


def test_expiry_and_renewal_request_flow() -> None:
    client = build_client()
    continuity = start_continuity(client, validity_days=1)
    expired_at = datetime.now(timezone.utc) + timedelta(days=2)
    expiry_response = client.post('/auron/demo1/v21.412/baseline/expire', json={
        'actor': 'master-brano',
        'continuity_id': continuity['continuity_id'],
        'expiry_phrase': 'EXPIRE AURON TELEGRAM RENEWED BASELINE',
        'expiry_reference': 'EXP-412',
        'expiry_statement': 'Baseline validity elapsed.',
        'expired_at': expired_at.isoformat(),
    })
    assert expiry_response.status_code == 200
    expiry = expiry_response.json()['expiry']
    assert expiry_response.json()['monitoring']['monitoring_state'] == 'successor-next-generation-nine-renewal-required'

    renewal_response = client.post('/auron/demo1/v21.412/renewal/request', json={
        'actor': 'master-brano',
        'expiry_id': expiry['expiry_id'],
        'renewal_phrase': 'REQUEST AURON TELEGRAM SUCCESSOR NEXT GENERATION NINE RENEWAL',
        'renewal_reference': 'RENEW-412',
        'renewal_statement': 'Request controlled successor renewal.',
    })
    assert renewal_response.status_code == 200
    assert renewal_response.json()['renewal_request']['renewal_state'] == 'successor-next-generation-nine-renewal-requested'
    assert renewal_response.json()['next_layer'] == 'successor-next-generation-ten-restoration-and-succession'
    assert renewal_response.json()['external_calls_made'] == 0


def test_command_center_available() -> None:
    response = build_client().get('/auron/demo1/v21.412/command-center')
    assert response.status_code == 200
    assert 'AURON TELEGRAM RENEWED BASELINE CONTINUITY COMMAND CENTER' in response.text
    assert 'no outbound message' in response.text
