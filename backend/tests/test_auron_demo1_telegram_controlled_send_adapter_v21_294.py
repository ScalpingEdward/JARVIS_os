from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_send_adapter_v21_294 as send
from app.api.routes import auron_demo1_telegram_conversation_router_v21_293 as conversation
from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()
    gateway.reset_telegram_gateway_runtime_store()
    provider.reset_telegram_provider_registration_store()
    conversation.reset_telegram_conversation_router_store()
    send.reset_telegram_controlled_send_store()


def _prepare() -> str:
    bridge.bind_telegram_chat(bridge.TelegramBindRequest(
        actor='brano', telegram_chat_id='1001', telegram_user_id='2001',
        operator_id='brano', workspace_id='master', pairing_code_verified=True,
    ))
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(
        actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
        webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-294',
        mode='webhook', enabled=True,
    ))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(
        actor='brano', webhook_registration_confirmed=True,
        provider_identity_verified=True, dry_run=True,
    ))
    bridge.ingest_telegram_message(bridge.TelegramInboundRequest(
        update_id='update-294', telegram_chat_id='1001', telegram_user_id='2001',
        message_id='message-294', text='Auron, Status bitte.',
    ))
    routed = conversation.route_telegram_conversation(
        conversation.TelegramConversationRouteRequest(actor='brano', update_id='update-294')
    )
    return routed['conversation']['correlation_id']


def test_send_dispatch_is_prepared_without_provider_call() -> None:
    correlation_id = _prepare()
    result = send.dispatch_telegram_reply(send.TelegramSendDispatchRequest(
        correlation_id=correlation_id, actor='brano',
        provider_identity_verified=True, transport_ready=True,
    ))
    assert result['state'] == 'telegram-send-dispatch-prepared'
    assert result['dispatch']['dispatch_state'] == 'prepared-not-called'
    assert result['dispatch']['provider_call_performed'] is False
    assert result['dispatch']['message_sent'] is False
    assert result['provider_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_dispatch_is_idempotent() -> None:
    correlation_id = _prepare()
    payload = send.TelegramSendDispatchRequest(
        correlation_id=correlation_id, actor='brano',
        provider_identity_verified=True, transport_ready=True,
    )
    first = send.dispatch_telegram_reply(payload)
    replay = send.dispatch_telegram_reply(payload)
    assert replay['state'] == 'telegram-send-dispatch-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['dispatch']['dispatch_id'] == first['dispatch']['dispatch_id']


def test_missing_transport_readiness_blocks_dispatch() -> None:
    correlation_id = _prepare()
    result = send.dispatch_telegram_reply(send.TelegramSendDispatchRequest(
        correlation_id=correlation_id, actor='brano',
        provider_identity_verified=True, transport_ready=False,
    ))
    assert result['state'] == 'telegram-send-dispatch-blocked'
    assert 'transport_ready' in result['blockers']
    assert result['external_calls_made'] == 0


def test_live_send_is_blocked() -> None:
    correlation_id = _prepare()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.294/dispatch', json={
        'correlation_id': correlation_id, 'actor': 'brano',
        'provider_identity_verified': True, 'transport_ready': True, 'dry_run': False,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.294/command-center')
    assert response.status_code == 200
    assert 'v21.294' in response.text
    assert 'AURON TELEGRAM CONTROLLED SEND ADAPTER COMMAND CENTER' in response.text
