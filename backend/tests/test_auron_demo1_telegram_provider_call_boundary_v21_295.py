from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_send_adapter_v21_294 as send
from app.api.routes import auron_demo1_telegram_conversation_router_v21_293 as conversation
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


def _prepare_dispatch() -> str:
    bridge.bind_telegram_chat(bridge.TelegramBindRequest(
        actor='brano', telegram_chat_id='1001', telegram_user_id='2001',
        operator_id='brano', workspace_id='master', pairing_code_verified=True,
    ))
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(
        actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
        webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-295',
        mode='webhook', enabled=True,
    ))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(
        actor='brano', webhook_registration_confirmed=True,
        provider_identity_verified=True, dry_run=True,
    ))
    bridge.ingest_telegram_message(bridge.TelegramInboundRequest(
        update_id='update-295', telegram_chat_id='1001', telegram_user_id='2001',
        message_id='message-295', text='Auron, Status bitte.',
    ))
    routed = conversation.route_telegram_conversation(
        conversation.TelegramConversationRouteRequest(actor='brano', update_id='update-295')
    )
    correlation_id = routed['conversation']['correlation_id']
    send.dispatch_telegram_reply(send.TelegramSendDispatchRequest(
        correlation_id=correlation_id, actor='brano',
        provider_identity_verified=True, transport_ready=True,
    ))
    return correlation_id


def test_provider_call_is_prepared_without_external_call() -> None:
    correlation_id = _prepare_dispatch()
    result = boundary.prepare_provider_call(boundary.TelegramProviderCallRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-provider-call-prepared'
    assert result['call']['method'] == 'sendMessage'
    assert result['call']['provider_call_performed'] is False
    assert result['provider_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_provider_call_preparation_is_idempotent() -> None:
    correlation_id = _prepare_dispatch()
    payload = boundary.TelegramProviderCallRequest(correlation_id=correlation_id, actor='brano')
    first = boundary.prepare_provider_call(payload)
    replay = boundary.prepare_provider_call(payload)
    assert replay['state'] == 'telegram-provider-call-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['call']['call_id'] == first['call']['call_id']


def test_accepted_receipt_is_verified_and_correlated() -> None:
    correlation_id = _prepare_dispatch()
    call = boundary.prepare_provider_call(boundary.TelegramProviderCallRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    result = boundary.verify_provider_receipt(boundary.TelegramProviderReceiptRequest(
        correlation_id=correlation_id, accepted=True, provider_message_id='telegram-message-295'
    ))
    assert result['state'] == 'telegram-provider-receipt-verified'
    assert result['receipt']['call_id'] == call['call']['call_id']
    assert result['receipt']['verification_state'] == 'accepted-awaiting-delivery-commit'
    assert result['next_layer'] == 'telegram-delivery-state-commit'
    assert result['external_calls_made'] == 0


def test_rejected_receipt_requires_error() -> None:
    correlation_id = _prepare_dispatch()
    boundary.prepare_provider_call(boundary.TelegramProviderCallRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.295/verify-receipt', json={
        'correlation_id': correlation_id, 'accepted': False
    })
    assert response.status_code == 422


def test_live_provider_call_is_blocked() -> None:
    correlation_id = _prepare_dispatch()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.295/prepare-call', json={
        'correlation_id': correlation_id, 'actor': 'brano', 'dry_run': False
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.295/command-center')
    assert response.status_code == 200
    assert 'v21.295' in response.text
    assert 'AURON TELEGRAM PROVIDER CALL BOUNDARY COMMAND CENTER' in response.text
