from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_retry_dispatch_v21_298 as dispatch
from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as original_commit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_retry_controller_v21_297 as retry
from app.api.routes import auron_demo1_telegram_retry_delivery_state_commit_v21_300 as commit
from app.api.routes import auron_demo1_telegram_retry_provider_call_boundary_v21_299 as boundary
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    original_commit.reset_telegram_delivery_state_commit_store()
    retry.reset_telegram_retry_controller_store()
    dispatch.reset_telegram_controlled_retry_dispatch_store()
    boundary.reset_telegram_retry_provider_call_boundary_store()
    commit.reset_telegram_retry_delivery_state_commit_store()


def _prepare_receipt(accepted: bool, error: str | None = None, attempt: int = 2, max_attempts: int = 3) -> str:
    correlation_id = 'correlation-300'
    retry_id = 'retry-300'
    retry_dispatch_id = 'retry-dispatch-300'
    original_commit._commit_store[correlation_id] = {
        'commit_id': 'commit-300', 'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled', 'terminal': False,
        'attempt': attempt - 1, 'max_attempts': max_attempts,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-300', 'correlation_id': correlation_id,
        'delivery_state': 'retry-dispatch-prepared',
    }
    retry._retry_store[f'{correlation_id}:{attempt}'] = {
        'retry_id': retry_id, 'correlation_id': correlation_id,
        'delivery_commit_id': 'commit-300', 'attempt': attempt,
        'max_attempts': max_attempts, 'retry_state': 'provider-call-prepared',
    }
    dispatch._retry_dispatch_store[retry_id] = {
        'retry_dispatch_id': retry_dispatch_id, 'retry_id': retry_id,
        'correlation_id': correlation_id, 'delivery_commit_id': 'commit-300',
        'outbound_id': 'outbound-300', 'provider_id': 'provider-300',
        'runtime_id': 'runtime-300', 'attempt': attempt,
        'max_attempts': max_attempts, 'telegram_chat_id': '1001',
        'text': 'AURON retry reply', 'reply_to_message_id': 'message-300',
        'dispatch_state': 'provider-call-prepared',
    }
    boundary._retry_call_store[retry_dispatch_id] = {
        'retry_call_id': 'retry-call-300', 'retry_dispatch_id': retry_dispatch_id,
        'retry_id': retry_id, 'correlation_id': correlation_id,
        'delivery_commit_id': 'commit-300', 'attempt': attempt,
        'max_attempts': max_attempts, 'call_state': 'prepared-not-executed',
    }
    boundary._retry_receipt_store[retry_dispatch_id] = {
        'retry_receipt_id': 'retry-receipt-300',
        'retry_dispatch_id': retry_dispatch_id,
        'retry_call_id': 'retry-call-300', 'retry_id': retry_id,
        'correlation_id': correlation_id, 'attempt': attempt,
        'accepted': accepted,
        'provider_message_id': 'telegram-message-300' if accepted else None,
        'provider_error': error,
        'verification_state': 'accepted-awaiting-retry-delivery-commit' if accepted else 'rejected-awaiting-retry-classification',
    }
    return retry_dispatch_id


def test_accepted_retry_receipt_commits_delivered_state() -> None:
    retry_dispatch_id = _prepare_receipt(True)
    result = commit.commit_telegram_retry_delivery(commit.TelegramRetryDeliveryCommitRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    assert result['commit']['delivery_state'] == 'delivered'
    assert result['commit']['terminal'] is True
    assert result['next_layer'] == 'telegram-terminal-delivery-audit'
    assert result['external_calls_made'] == 0


def test_retryable_failure_before_budget_schedules_another_retry() -> None:
    retry_dispatch_id = _prepare_receipt(False, 'temporary network timeout', attempt=2, max_attempts=3)
    result = commit.commit_telegram_retry_delivery(commit.TelegramRetryDeliveryCommitRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    assert result['commit']['delivery_state'] == 'retry-scheduled'
    assert result['commit']['terminal'] is False
    assert result['next_layer'] == 'telegram-send-retry-controller'


def test_retryable_failure_at_budget_becomes_exhausted() -> None:
    retry_dispatch_id = _prepare_receipt(False, 'rate limit 429', attempt=3, max_attempts=3)
    result = commit.commit_telegram_retry_delivery(commit.TelegramRetryDeliveryCommitRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    assert result['commit']['delivery_state'] == 'retry-exhausted'
    assert result['commit']['terminal'] is True


def test_permanent_failure_is_terminal() -> None:
    retry_dispatch_id = _prepare_receipt(False, 'chat not found')
    result = commit.commit_telegram_retry_delivery(commit.TelegramRetryDeliveryCommitRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    assert result['commit']['delivery_state'] == 'permanent-failure'
    assert result['commit']['terminal'] is True


def test_retry_delivery_commit_is_idempotent() -> None:
    retry_dispatch_id = _prepare_receipt(True)
    payload = commit.TelegramRetryDeliveryCommitRequest(retry_dispatch_id=retry_dispatch_id, actor='brano')
    first = commit.commit_telegram_retry_delivery(payload)
    replay = commit.commit_telegram_retry_delivery(payload)
    assert replay['idempotent_replay'] is True
    assert replay['commit']['retry_delivery_commit_id'] == first['commit']['retry_delivery_commit_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.300/command-center')
    assert response.status_code == 200
    assert 'v21.300' in response.text
    assert 'AURON TELEGRAM RETRY DELIVERY STATE COMMIT COMMAND CENTER' in response.text
