from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as commit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_retry_controller_v21_297 as retry
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    commit.reset_telegram_delivery_state_commit_store()
    retry.reset_telegram_retry_controller_store()


def _retryable_commit(attempt: int = 1, max_attempts: int = 3) -> str:
    correlation_id = 'retry-297'
    commit._commit_store[correlation_id] = {
        'commit_id': 'commit-297',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled',
        'terminal': False,
        'attempt': attempt,
        'max_attempts': max_attempts,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-297',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled',
    }
    return correlation_id


def test_retry_is_scheduled_with_next_attempt_and_backoff() -> None:
    correlation_id = _retryable_commit()
    result = retry.schedule_telegram_retry(retry.TelegramRetryScheduleRequest(
        correlation_id=correlation_id, actor='brano', backoff_seconds=45,
    ))
    assert result['state'] == 'telegram-retry-scheduled'
    assert result['retry']['previous_attempt'] == 1
    assert result['retry']['attempt'] == 2
    assert result['retry']['backoff_seconds'] == 45
    assert result['retry']['retry_state'] == 'scheduled'
    assert result['retry']['provider_call_performed'] is False
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_same_retry_schedule_is_idempotent() -> None:
    correlation_id = _retryable_commit()
    payload = retry.TelegramRetryScheduleRequest(correlation_id=correlation_id, actor='brano')
    first = retry.schedule_telegram_retry(payload)
    replay = retry.schedule_telegram_retry(payload)
    assert replay['state'] == 'telegram-retry-already-scheduled'
    assert replay['idempotent_replay'] is True
    assert replay['retry']['retry_id'] == first['retry']['retry_id']


def test_retry_budget_exhaustion_becomes_terminal() -> None:
    correlation_id = _retryable_commit(attempt=3, max_attempts=3)
    result = retry.schedule_telegram_retry(retry.TelegramRetryScheduleRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-retry-budget-exhausted'
    assert result['retry']['retry_state'] == 'exhausted'
    assert commit._commit_store[correlation_id]['delivery_state'] == 'retry-exhausted'
    assert commit._commit_store[correlation_id]['terminal'] is True
    assert provider._outbound_store[correlation_id]['delivery_state'] == 'retry-exhausted'
    assert result['next_layer'] == 'telegram-delivery-audit'


def test_non_retryable_commit_is_rejected() -> None:
    correlation_id = _retryable_commit()
    commit._commit_store[correlation_id]['delivery_state'] = 'permanent-failure'
    commit._commit_store[correlation_id]['terminal'] = True
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.297/schedule', json={
        'correlation_id': correlation_id, 'actor': 'brano', 'dry_run': True,
    })
    assert response.status_code == 409


def test_live_retry_execution_is_blocked() -> None:
    correlation_id = _retryable_commit()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.297/schedule', json={
        'correlation_id': correlation_id, 'actor': 'brano', 'dry_run': False,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.297/command-center')
    assert response.status_code == 200
    assert 'v21.297' in response.text
    assert 'AURON TELEGRAM RETRY CONTROLLER COMMAND CENTER' in response.text
