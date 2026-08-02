from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_send_adapter_v21_294 as send
from app.api.routes import auron_demo1_telegram_conversation_router_v21_293 as conversation
from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as commit
from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_provider_call_boundary_v21_295 as boundary
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()
    gateway.reset_telegram_gateway_runtime_store()
    provider.reset_telegram_provider_registration_store()
    conversation.reset_telegram_conversation_router_store()
    send.reset_telegram_controlled_send_store()
    boundary.reset_telegram_provider_call_boundary_store()
    commit.reset_telegram_delivery_state_commit_store()


def _receipt(accepted: bool, error: str | None = None) -> str:
    bridge.bind_telegram_chat(bridge.TelegramBindRequest(actor='brano', telegram_chat_id='1001', telegram_user_id='2001', operator_id='brano', workspace_id='master', pairing_code_verified=True))
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz', webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-296', mode='webhook', enabled=True))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(actor='brano', webhook_registration_confirmed=True, provider_identity_verified=True))
    bridge.ingest_telegram_message(bridge.TelegramInboundRequest(update_id='update-296', telegram_chat_id='1001', telegram_user_id='2001', message_id='message-296', text='Auron Status'))
    routed = conversation.route_telegram_conversation(conversation.TelegramConversationRouteRequest(actor='brano', update_id='update-296'))
    correlation_id = routed['conversation']['correlation_id']
    send.dispatch_telegram_reply(send.TelegramSendDispatchRequest(correlation_id=correlation_id, actor='brano', provider_identity_verified=True, transport_ready=True))
    boundary.prepare_provider_call(boundary.TelegramProviderCallRequest(correlation_id=correlation_id, actor='brano'))
    boundary.verify_provider_receipt(boundary.TelegramProviderReceiptRequest(correlation_id=correlation_id, accepted=accepted, provider_message_id='tg-296' if accepted else None, provider_error=error))
    return correlation_id


def test_accepted_receipt_commits_delivered_state() -> None:
    correlation_id = _receipt(True)
    result = commit.commit_telegram_delivery(commit.TelegramDeliveryCommitRequest(correlation_id=correlation_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'delivered'
    assert result['commit']['terminal'] is True
    assert result['next_layer'] == 'telegram-delivery-audit'
    assert result['external_calls_made'] == 0


def test_retryable_rejection_is_scheduled() -> None:
    correlation_id = _receipt(False, 'temporary network timeout')
    result = commit.commit_telegram_delivery(commit.TelegramDeliveryCommitRequest(correlation_id=correlation_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'retry-scheduled'
    assert result['commit']['rejection_class'] == 'retryable'
    assert result['commit']['terminal'] is False


def test_permanent_rejection_is_terminal() -> None:
    correlation_id = _receipt(False, 'chat not found')
    result = commit.commit_telegram_delivery(commit.TelegramDeliveryCommitRequest(correlation_id=correlation_id, actor='brano'))
    assert result['commit']['delivery_state'] == 'permanent-failure'
    assert result['commit']['terminal'] is True


def test_delivery_commit_is_idempotent() -> None:
    correlation_id = _receipt(True)
    payload = commit.TelegramDeliveryCommitRequest(correlation_id=correlation_id, actor='brano')
    first = commit.commit_telegram_delivery(payload)
    replay = commit.commit_telegram_delivery(payload)
    assert replay['idempotent_replay'] is True
    assert replay['commit']['commit_id'] == first['commit']['commit_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.296/command-center')
    assert response.status_code == 200
    assert 'v21.296' in response.text
    assert 'AURON TELEGRAM DELIVERY STATE COMMIT COMMAND CENTER' in response.text
