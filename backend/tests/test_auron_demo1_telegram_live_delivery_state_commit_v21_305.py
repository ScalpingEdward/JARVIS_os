from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_live_transport_adapter_v21_304 as live
from app.api.routes import auron_demo1_telegram_controlled_send_adapter_v21_294 as send
from app.api.routes import auron_demo1_telegram_live_delivery_state_commit_v21_305 as commit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    send.reset_telegram_controlled_send_store()
    live.reset_telegram_controlled_live_transport_adapter_store()
    commit.reset_telegram_live_delivery_state_commit_store()


def _prepare_receipt(accepted: bool, error: str | None = None, http_status: int = 200) -> str:
    correlation_id = 'correlation-305'
    execution_id = 'execution-305'
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-305',
        'correlation_id': correlation_id,
        'delivery_state': 'live-execution-authorized',
    }
    send._dispatch_store[correlation_id] = {
        'dispatch_id': 'dispatch-305',
        'correlation_id': correlation_id,
        'dispatch_state': 'live-execution-authorized',
    }
    live._live_execution_store[correlation_id] = {
        'execution_id': execution_id,
        'correlation_id': correlation_id,
        'activation_id': 'activation-305',
        'provider_id': 'provider-305',
        'runtime_id': 'runtime-305',
        'outbound_id': 'outbound-305',
        'dispatch_id': 'dispatch-305',
        'execution_state': 'provider-receipt-captured',
    }
    live._live_receipt_store[execution_id] = {
        'receipt_id': 'receipt-305',
        'execution_id': execution_id,
        'correlation_id': correlation_id,
        'accepted': accepted,
        'provider_message_id': 'telegram-message-305' if accepted else None,
        'provider_error': error,
        'http_status': http_status,
    }
    return execution_id


def test_accepted_live_receipt_commits_delivered() -> None:
    execution_id = _prepare_receipt(True)
    result = commit.commit_live_delivery(commit.TelegramLiveDeliveryCommitRequest(execution_id=execution_id, actor='brano'))
    assert result['state'] == 'telegram-live-delivery-state-committed'
    assert result['commit']['delivery_state'] == 'delivered'
    assert result['commit']['terminal'] is True
    assert result['next_layer'] == 'telegram-live-terminal-audit'
    assert result['external_calls_made'] == 0


def test_retryable_live_failure_requires_retry() -> None:
    execution_id = _prepare_receipt(False, 'temporary network timeout', 503)
    result = commit.commit_live_delivery(commit.TelegramLiveDeliveryCommitRequest(execution_id=execution_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'retry-required'
    assert result['commit']['failure_class'] == 'retryable'
    assert result['commit']['terminal'] is False
    assert result['next_layer'] == 'telegram-live-retry-controller'


def test_permanent_live_failure_is_terminal() -> None:
    execution_id = _prepare_receipt(False, 'chat not found', 400)
    result = commit.commit_live_delivery(commit.TelegramLiveDeliveryCommitRequest(execution_id=execution_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'permanent-failure'
    assert result['commit']['failure_class'] == 'permanent'
    assert result['commit']['terminal'] is True


def test_live_delivery_commit_is_idempotent() -> None:
    execution_id = _prepare_receipt(True)
    payload = commit.TelegramLiveDeliveryCommitRequest(execution_id=execution_id, actor='brano')
    first = commit.commit_live_delivery(payload)
    replay = commit.commit_live_delivery(payload)
    assert replay['idempotent_replay'] is True
    assert replay['commit']['live_delivery_commit_id'] == first['commit']['live_delivery_commit_id']


def test_missing_receipt_is_rejected() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.305/commit', json={'execution_id': 'missing', 'actor': 'brano'})
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.305/command-center')
    assert response.status_code == 200
    assert 'v21.305' in response.text
    assert 'AURON TELEGRAM LIVE DELIVERY STATE COMMIT COMMAND CENTER' in response.text
