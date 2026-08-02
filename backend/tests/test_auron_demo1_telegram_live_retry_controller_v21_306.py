from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_live_transport_adapter_v21_304 as live
from app.api.routes import auron_demo1_telegram_live_delivery_state_commit_v21_305 as commit
from app.api.routes import auron_demo1_telegram_live_retry_controller_v21_306 as retry
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    live.reset_telegram_controlled_live_transport_adapter_store()
    commit.reset_telegram_live_delivery_state_commit_store()
    retry.reset_telegram_live_retry_controller_store()


def _retryable_chain(previous_attempt: int = 1) -> str:
    correlation_id = 'correlation-306'
    execution_id = 'execution-306'
    commit_id = 'live-commit-306'
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-306',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-required',
    }
    live._live_execution_store[correlation_id] = {
        'execution_id': execution_id,
        'correlation_id': correlation_id,
        'live_delivery_commit_id': commit_id,
        'execution_state': 'delivery-committed',
        'attempt': previous_attempt,
    }
    commit._live_delivery_commit_store[execution_id] = {
        'live_delivery_commit_id': commit_id,
        'execution_id': execution_id,
        'correlation_id': correlation_id,
        'activation_id': 'activation-306',
        'provider_id': 'provider-306',
        'runtime_id': 'runtime-306',
        'outbound_id': 'outbound-306',
        'dispatch_id': 'dispatch-306',
        'delivery_state': 'retry-required',
        'terminal': False,
    }
    return commit_id


def test_retryable_live_commit_is_scheduled_with_backoff() -> None:
    commit_id = _retryable_chain()
    result = retry.schedule_live_retry(retry.TelegramLiveRetryScheduleRequest(
        live_delivery_commit_id=commit_id, actor='brano', max_attempts=3, base_backoff_seconds=30
    ))
    assert result['state'] == 'telegram-live-retry-scheduled'
    assert result['retry']['attempt'] == 2
    assert result['retry']['eligible_at'] is not None
    assert result['retry']['terminal'] is False
    assert result['next_layer'] == 'telegram-live-controlled-retry-dispatch'
    assert result['external_calls_made'] == 0


def test_retry_budget_exhaustion_becomes_terminal() -> None:
    commit_id = _retryable_chain(previous_attempt=3)
    result = retry.schedule_live_retry(retry.TelegramLiveRetryScheduleRequest(
        live_delivery_commit_id=commit_id, actor='brano', max_attempts=3
    ))
    assert result['state'] == 'telegram-live-retry-exhausted'
    assert result['retry']['retry_state'] == 'retry-exhausted'
    assert result['retry']['terminal'] is True
    assert result['retry']['eligible_at'] is None
    assert result['next_layer'] == 'telegram-live-terminal-audit'


def test_live_retry_schedule_is_idempotent() -> None:
    commit_id = _retryable_chain()
    payload = retry.TelegramLiveRetryScheduleRequest(live_delivery_commit_id=commit_id, actor='brano')
    first = retry.schedule_live_retry(payload)
    replay = retry.schedule_live_retry(payload)
    assert replay['idempotent_replay'] is True
    assert replay['retry']['live_retry_id'] == first['retry']['live_retry_id']


def test_terminal_commit_cannot_be_retried() -> None:
    commit_id = _retryable_chain()
    commit._live_delivery_commit_store['execution-306']['delivery_state'] = 'permanent-failure'
    commit._live_delivery_commit_store['execution-306']['terminal'] = True
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.306/schedule', json={
        'live_delivery_commit_id': commit_id, 'actor': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.306/command-center')
    assert response.status_code == 200
    assert 'v21.306' in response.text
    assert 'AURON TELEGRAM LIVE RETRY CONTROLLER COMMAND CENTER' in response.text
