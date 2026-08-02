from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_live_controlled_retry_dispatch_v21_307 as dispatch
from app.api.routes import auron_demo1_telegram_live_retry_controller_v21_306 as retry
from app.api.routes import auron_demo1_telegram_live_retry_receipt_commit_v21_308 as commit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    retry.reset_telegram_live_retry_controller_store()
    dispatch.reset_telegram_live_controlled_retry_dispatch_store()
    commit.reset_telegram_live_retry_receipt_commit_store()


def _chain(attempt: int = 2, max_attempts: int = 3) -> str:
    correlation_id = 'correlation-308'
    retry_id = 'retry-308'
    dispatch_id = 'retry-dispatch-308'
    provider._outbound_store[correlation_id] = {'outbound_id': 'outbound-308', 'correlation_id': correlation_id, 'delivery_state': 'retry-dispatch-prepared'}
    retry._live_retry_store['live-commit-308'] = {
        'live_retry_id': retry_id, 'live_delivery_commit_id': 'live-commit-308',
        'correlation_id': correlation_id, 'retry_state': 'dispatch-prepared', 'terminal': False,
    }
    dispatch._live_retry_dispatch_store[retry_id] = {
        'live_retry_dispatch_id': dispatch_id, 'live_retry_id': retry_id,
        'live_delivery_commit_id': 'live-commit-308', 'correlation_id': correlation_id,
        'provider_id': 'provider-308', 'runtime_id': 'runtime-308',
        'outbound_id': 'outbound-308', 'attempt': attempt, 'max_attempts': max_attempts,
        'dispatch_state': 'authorized-awaiting-runtime-worker',
    }
    return dispatch_id


def _capture(dispatch_id: str, accepted: bool, error: str | None = None, status: int = 200):
    return commit.capture_live_retry_receipt(commit.TelegramLiveRetryReceiptRequest(
        live_retry_dispatch_id=dispatch_id, accepted=accepted,
        provider_message_id='telegram-message-308' if accepted else None,
        provider_error=error, http_status=status,
    ))


def test_accepted_retry_receipt_commits_delivered() -> None:
    dispatch_id = _chain()
    _capture(dispatch_id, True)
    result = commit.commit_live_retry_delivery(commit.TelegramLiveRetryCommitRequest(live_retry_dispatch_id=dispatch_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'delivered'
    assert result['commit']['terminal'] is True
    assert result['next_layer'] == 'telegram-live-terminal-audit'
    assert result['external_calls_made'] == 0


def test_retryable_failure_before_limit_requires_another_retry() -> None:
    dispatch_id = _chain(attempt=2, max_attempts=3)
    _capture(dispatch_id, False, 'temporary network timeout', 503)
    result = commit.commit_live_retry_delivery(commit.TelegramLiveRetryCommitRequest(live_retry_dispatch_id=dispatch_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'retry-required'
    assert result['commit']['terminal'] is False
    assert result['next_layer'] == 'telegram-live-retry-controller'


def test_retryable_failure_at_limit_is_exhausted() -> None:
    dispatch_id = _chain(attempt=3, max_attempts=3)
    _capture(dispatch_id, False, 'rate limit', 429)
    result = commit.commit_live_retry_delivery(commit.TelegramLiveRetryCommitRequest(live_retry_dispatch_id=dispatch_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'retry-exhausted'
    assert result['commit']['terminal'] is True


def test_permanent_failure_is_terminal() -> None:
    dispatch_id = _chain()
    _capture(dispatch_id, False, 'chat not found', 400)
    result = commit.commit_live_retry_delivery(commit.TelegramLiveRetryCommitRequest(live_retry_dispatch_id=dispatch_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'permanent-failure'
    assert result['commit']['failure_class'] == 'permanent'


def test_receipt_and_commit_are_idempotent() -> None:
    dispatch_id = _chain()
    first_receipt = _capture(dispatch_id, True)
    replay_receipt = _capture(dispatch_id, True)
    assert replay_receipt['idempotent_replay'] is True
    assert replay_receipt['receipt']['live_retry_receipt_id'] == first_receipt['receipt']['live_retry_receipt_id']
    payload = commit.TelegramLiveRetryCommitRequest(live_retry_dispatch_id=dispatch_id, actor='brano')
    first_commit = commit.commit_live_retry_delivery(payload)
    replay_commit = commit.commit_live_retry_delivery(payload)
    assert replay_commit['idempotent_replay'] is True
    assert replay_commit['commit']['live_retry_delivery_commit_id'] == first_commit['commit']['live_retry_delivery_commit_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.308/command-center')
    assert response.status_code == 200
    assert 'v21.308' in response.text
    assert 'AURON TELEGRAM LIVE RETRY RECEIPT COMMIT COMMAND CENTER' in response.text
