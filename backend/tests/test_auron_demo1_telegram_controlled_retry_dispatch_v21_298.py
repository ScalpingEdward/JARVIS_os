from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_retry_dispatch_v21_298 as dispatch
from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as commit
from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_retry_controller_v21_297 as retry
from app.main import app


def setup_function() -> None:
    gateway.reset_telegram_gateway_runtime_store()
    provider.reset_telegram_provider_registration_store()
    commit.reset_telegram_delivery_state_commit_store()
    retry.reset_telegram_retry_controller_store()
    dispatch.reset_telegram_controlled_retry_dispatch_store()


def _prepare_retry(eligible: bool = True) -> dict:
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(
        actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
        webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-298',
        mode='webhook', enabled=True,
    ))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(
        actor='brano', webhook_registration_confirmed=True,
        provider_identity_verified=True, dry_run=True,
    ))
    correlation_id = 'retry-298'
    commit._commit_store[correlation_id] = {
        'commit_id': 'commit-298', 'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled', 'terminal': False,
        'attempt': 1, 'max_attempts': 3,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-298', 'correlation_id': correlation_id,
        'telegram_chat_id': '1001', 'text': 'AURON Antwort',
        'reply_to_message_id': 'message-298', 'delivery_state': 'retry-scheduled',
    }
    scheduled = retry.schedule_telegram_retry(retry.TelegramRetryScheduleRequest(
        correlation_id=correlation_id, actor='brano', backoff_seconds=30,
    ))['retry']
    scheduled['eligible_at'] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
        if eligible else datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    return scheduled


def test_eligible_retry_dispatch_is_prepared_without_provider_call() -> None:
    scheduled = _prepare_retry()
    result = dispatch.dispatch_telegram_retry(dispatch.TelegramRetryDispatchRequest(
        retry_id=scheduled['retry_id'], actor='brano'
    ))
    assert result['state'] == 'telegram-retry-dispatch-prepared'
    assert result['retry_dispatch']['attempt'] == 2
    assert result['retry_dispatch']['dispatch_state'] == 'prepared-not-called'
    assert result['retry_dispatch']['provider_call_performed'] is False
    assert result['retry_dispatch']['message_sent'] is False
    assert result['provider_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_retry_dispatch_is_idempotent() -> None:
    scheduled = _prepare_retry()
    payload = dispatch.TelegramRetryDispatchRequest(retry_id=scheduled['retry_id'], actor='brano')
    first = dispatch.dispatch_telegram_retry(payload)
    replay = dispatch.dispatch_telegram_retry(payload)
    assert replay['state'] == 'telegram-retry-dispatch-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['retry_dispatch']['retry_dispatch_id'] == first['retry_dispatch']['retry_dispatch_id']


def test_retry_before_eligibility_is_not_dispatched() -> None:
    scheduled = _prepare_retry(eligible=False)
    result = dispatch.dispatch_telegram_retry(dispatch.TelegramRetryDispatchRequest(
        retry_id=scheduled['retry_id'], actor='brano'
    ))
    assert result['state'] == 'telegram-retry-dispatch-not-yet-eligible'
    assert result['external_calls_made'] == 0


def test_live_retry_dispatch_is_blocked() -> None:
    scheduled = _prepare_retry()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.298/dispatch', json={
        'retry_id': scheduled['retry_id'], 'actor': 'brano', 'dry_run': False,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.298/command-center')
    assert response.status_code == 200
    assert 'v21.298' in response.text
    assert 'AURON TELEGRAM CONTROLLED RETRY DISPATCH COMMAND CENTER' in response.text
