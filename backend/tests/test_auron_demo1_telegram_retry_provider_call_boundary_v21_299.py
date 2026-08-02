from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_retry_dispatch_v21_298 as dispatch
from app.api.routes import auron_demo1_telegram_retry_controller_v21_297 as retry
from app.api.routes import auron_demo1_telegram_retry_provider_call_boundary_v21_299 as boundary
from app.main import app


def setup_function() -> None:
    retry.reset_telegram_retry_controller_store()
    dispatch.reset_telegram_controlled_retry_dispatch_store()
    boundary.reset_telegram_retry_provider_call_boundary_store()


def _prepare_dispatch() -> str:
    retry._retry_store['correlation-299:2'] = {
        'retry_id': 'retry-299',
        'correlation_id': 'correlation-299',
        'delivery_commit_id': 'commit-299',
        'attempt': 2,
        'max_attempts': 3,
        'retry_state': 'dispatch-prepared',
    }
    dispatch._retry_dispatch_store['retry-299'] = {
        'retry_dispatch_id': 'retry-dispatch-299',
        'retry_id': 'retry-299',
        'correlation_id': 'correlation-299',
        'delivery_commit_id': 'commit-299',
        'outbound_id': 'outbound-299',
        'provider_id': 'provider-299',
        'runtime_id': 'runtime-299',
        'attempt': 2,
        'max_attempts': 3,
        'telegram_chat_id': '1001',
        'text': 'AURON retry reply',
        'reply_to_message_id': 'message-299',
        'dispatch_state': 'prepared-not-called',
    }
    return 'retry-dispatch-299'


def test_retry_provider_call_is_prepared_without_external_call() -> None:
    retry_dispatch_id = _prepare_dispatch()
    result = boundary.prepare_retry_provider_call(boundary.TelegramRetryProviderCallRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    assert result['state'] == 'telegram-retry-provider-call-prepared'
    assert result['call']['method'] == 'sendMessage'
    assert result['call']['attempt'] == 2
    assert result['call']['provider_call_performed'] is False
    assert result['provider_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_retry_provider_call_is_idempotent() -> None:
    retry_dispatch_id = _prepare_dispatch()
    payload = boundary.TelegramRetryProviderCallRequest(retry_dispatch_id=retry_dispatch_id, actor='brano')
    first = boundary.prepare_retry_provider_call(payload)
    replay = boundary.prepare_retry_provider_call(payload)
    assert replay['state'] == 'telegram-retry-provider-call-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['call']['retry_call_id'] == first['call']['retry_call_id']


def test_accepted_retry_receipt_is_verified() -> None:
    retry_dispatch_id = _prepare_dispatch()
    boundary.prepare_retry_provider_call(boundary.TelegramRetryProviderCallRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    result = boundary.verify_retry_provider_receipt(boundary.TelegramRetryProviderReceiptRequest(
        retry_dispatch_id=retry_dispatch_id, accepted=True, provider_message_id='telegram-retry-message-299'
    ))
    assert result['state'] == 'telegram-retry-provider-receipt-verified'
    assert result['receipt']['verification_state'] == 'accepted-awaiting-retry-delivery-commit'
    assert result['next_layer'] == 'telegram-retry-delivery-state-commit'
    assert result['external_calls_made'] == 0


def test_rejected_retry_receipt_requires_provider_error() -> None:
    retry_dispatch_id = _prepare_dispatch()
    boundary.prepare_retry_provider_call(boundary.TelegramRetryProviderCallRequest(
        retry_dispatch_id=retry_dispatch_id, actor='brano'
    ))
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.299/verify-receipt', json={
        'retry_dispatch_id': retry_dispatch_id, 'accepted': False
    })
    assert response.status_code == 422


def test_live_retry_provider_call_is_blocked() -> None:
    retry_dispatch_id = _prepare_dispatch()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.299/prepare-call', json={
        'retry_dispatch_id': retry_dispatch_id, 'actor': 'brano', 'dry_run': False
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.299/command-center')
    assert response.status_code == 200
    assert 'v21.299' in response.text
    assert 'AURON TELEGRAM RETRY PROVIDER CALL BOUNDARY COMMAND CENTER' in response.text
