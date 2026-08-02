from fastapi.testclient import TestClient

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


def _prepare_text_message() -> None:
    bridge.bind_telegram_chat(bridge.TelegramBindRequest(
        actor='brano', telegram_chat_id='1001', telegram_user_id='2001',
        operator_id='brano', workspace_id='master', pairing_code_verified=True,
    ))
    gateway.configure_telegram_runtime(gateway.TelegramRuntimeConfigureRequest(
        actor='brano', bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
        webhook_base_url='https://auron.example.com', webhook_secret='telegram-secret-293',
        mode='webhook', enabled=True,
    ))
    provider.register_telegram_provider(provider.TelegramProviderRegisterRequest(
        actor='brano', webhook_registration_confirmed=True,
        provider_identity_verified=True, dry_run=True,
    ))
    bridge.ingest_telegram_message(bridge.TelegramInboundRequest(
        update_id='update-293', telegram_chat_id='1001', telegram_user_id='2001',
        message_id='message-293', text='Auron, wie ist der System Status?',
    ))


def test_text_message_is_routed_and_reply_prepared_without_send() -> None:
    _prepare_text_message()
    result = conversation.route_telegram_conversation(
        conversation.TelegramConversationRouteRequest(actor='brano', update_id='update-293')
    )
    assert result['state'] == 'telegram-conversation-routed'
    assert result['conversation']['intent'] == 'system-status'
    assert result['conversation']['dialogue_request_created'] is True
    assert result['conversation']['model_invoked'] is False
    assert result['conversation']['reply_prepared'] is True
    assert result['conversation']['reply_sent'] is False
    assert result['outbound']['delivery_state'] == 'prepared-not-sent'
    assert result['model_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_conversation_routing_is_idempotent() -> None:
    _prepare_text_message()
    payload = conversation.TelegramConversationRouteRequest(actor='brano', update_id='update-293')
    first = conversation.route_telegram_conversation(payload)
    replay = conversation.route_telegram_conversation(payload)
    assert replay['state'] == 'telegram-conversation-already-routed'
    assert replay['idempotent_replay'] is True
    assert replay['conversation']['conversation_id'] == first['conversation']['conversation_id']


def test_voice_message_is_not_routed_as_text() -> None:
    _prepare_text_message()
    bridge.ingest_telegram_message(bridge.TelegramInboundRequest(
        update_id='voice-293', telegram_chat_id='1001', telegram_user_id='2001',
        message_id='voice-message-293', voice_file_id='voice-file-293',
    ))
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.293/route', json={
        'actor': 'brano', 'update_id': 'voice-293', 'dry_run': True,
    })
    assert response.status_code == 409


def test_live_delivery_is_blocked() -> None:
    _prepare_text_message()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.293/route', json={
        'actor': 'brano', 'update_id': 'update-293', 'dry_run': False,
    })
    assert response.status_code == 409


def test_custom_governed_response_is_preserved() -> None:
    _prepare_text_message()
    result = conversation.route_telegram_conversation(
        conversation.TelegramConversationRouteRequest(
            actor='brano', update_id='update-293', response_text='Alles bereit, Master Brano.'
        )
    )
    assert result['conversation']['response_text'] == 'Alles bereit, Master Brano.'
    assert result['outbound']['text'] == 'Alles bereit, Master Brano.'


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.293/command-center')
    assert response.status_code == 200
    assert 'v21.293' in response.text
    assert 'AURON TELEGRAM CONVERSATION ROUTER COMMAND CENTER' in response.text
