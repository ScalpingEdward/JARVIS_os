from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_live_controlled_retry_dispatch_v21_307 as dispatch
from app.api.routes import auron_demo1_telegram_live_retry_controller_v21_306 as retry
from app.api.routes import auron_demo1_telegram_production_activation_gate_v21_303 as gate
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    gate.reset_telegram_production_activation_gate_store()
    retry.reset_telegram_live_retry_controller_store()
    dispatch.reset_telegram_live_controlled_retry_dispatch_store()


def _ready_chain(eligible: bool = True) -> tuple[str, str]:
    live_retry_id = 'live-retry-307'
    correlation_id = 'correlation-307'
    provider._provider_store['provider-307'] = {
        'provider_id': 'provider-307',
        'runtime_id': 'runtime-307',
        'provider_ready': True,
        'active': True,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-307',
        'correlation_id': correlation_id,
        'telegram_chat_id': '1001',
        'text': 'Retry von AURON',
        'reply_to_message_id': 'message-307',
        'parse_mode': None,
        'disable_notification': False,
        'delivery_state': 'retry-scheduled',
    }
    gate._activation_store['runtime-307:provider-307:brano'] = {
        'activation_id': 'activation-307',
        'provider_id': 'provider-307',
        'runtime_id': 'runtime-307',
        'production_transport_authorized': True,
        'active': True,
    }
    now = datetime.now(timezone.utc)
    retry._live_retry_store['live-commit-307'] = {
        'live_retry_id': live_retry_id,
        'live_delivery_commit_id': 'live-commit-307',
        'execution_id': 'execution-307',
        'correlation_id': correlation_id,
        'activation_id': 'activation-307',
        'provider_id': 'provider-307',
        'runtime_id': 'runtime-307',
        'outbound_id': 'outbound-307',
        'dispatch_id': 'dispatch-307',
        'attempt': 2,
        'max_attempts': 3,
        'eligible_at': (now - timedelta(seconds=1) if eligible else now + timedelta(minutes=5)).isoformat(),
        'retry_state': 'scheduled',
        'terminal': False,
    }
    return live_retry_id, now.isoformat()


def _payload(live_retry_id: str, now_iso: str, **overrides):
    values = {
        'live_retry_id': live_retry_id,
        'actor': 'brano',
        'execution_phrase': 'EXECUTE ONE AURON TELEGRAM RETRY',
        'credentials_loaded_in_runtime': True,
        'network_egress_available': True,
        'now_iso': now_iso,
    }
    values.update(overrides)
    return dispatch.TelegramLiveRetryDispatchRequest(**values)


def test_eligible_retry_creates_single_provider_execution_contract() -> None:
    live_retry_id, now_iso = _ready_chain()
    result = dispatch.dispatch_live_retry(_payload(live_retry_id, now_iso))
    assert result['state'] == 'telegram-live-retry-dispatch-prepared'
    assert result['dispatch']['attempt'] == 2
    assert result['dispatch']['method'] == 'sendMessage'
    assert result['dispatch']['provider_call_performed'] is False
    assert result['next_layer'] == 'telegram-live-retry-runtime-worker-provider-call'
    assert result['external_calls_made'] == 0


def test_retry_dispatch_is_idempotent() -> None:
    live_retry_id, now_iso = _ready_chain()
    payload = _payload(live_retry_id, now_iso)
    first = dispatch.dispatch_live_retry(payload)
    replay = dispatch.dispatch_live_retry(payload)
    assert replay['idempotent_replay'] is True
    assert replay['dispatch']['live_retry_dispatch_id'] == first['dispatch']['live_retry_dispatch_id']


def test_retry_before_eligible_at_is_blocked() -> None:
    live_retry_id, now_iso = _ready_chain(eligible=False)
    result = dispatch.dispatch_live_retry(_payload(live_retry_id, now_iso))
    assert result['state'] == 'telegram-live-retry-dispatch-blocked'
    assert 'retry_eligible' in result['blockers']
    assert result['external_calls_made'] == 0


def test_missing_runtime_readiness_blocks_dispatch() -> None:
    live_retry_id, now_iso = _ready_chain()
    result = dispatch.dispatch_live_retry(_payload(live_retry_id, now_iso, network_egress_available=False))
    assert result['state'] == 'telegram-live-retry-dispatch-blocked'
    assert 'network_egress_available' in result['blockers']


def test_wrong_execution_phrase_is_rejected() -> None:
    live_retry_id, now_iso = _ready_chain()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.307/dispatch', json={
        **_payload(live_retry_id, now_iso).model_dump(),
        'execution_phrase': 'wrong phrase',
    })
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.307/command-center')
    assert response.status_code == 200
    assert 'v21.307' in response.text
    assert 'AURON TELEGRAM LIVE CONTROLLED RETRY DISPATCH COMMAND CENTER' in response.text
