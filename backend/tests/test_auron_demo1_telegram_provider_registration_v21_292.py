from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()
    gateway.reset_telegram_gateway_runtime_store()
    provider.reset_telegram_provider_registration_store()


def _bind() -> None:
    bridge.bind_telegram_chat(
        bridge.TelegramBindRequest(
            actor='brano',
            telegram_chat_id='1001',
            telegram_user_id='2001',
            operator_id='brano',
            workspace_id='master',
            pairing_code_verified=True,
        )
    )


def _runtime() -> None:
    gateway.configure_telegram_runtime(
        gateway.TelegramRuntimeConfigureRequest(
            actor='brano',
            bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
            webhook_base_url='https://auron.example.com',
            webhook_secret='telegram-webhook-secret-292',
            mode='webhook',
            enabled=True,
        )
    )


def _provider(ready: bool = True) -> dict:
    return provider.register_telegram_provider(
        provider.TelegramProviderRegisterRequest(
            actor='brano',
            webhook_registration_confirmed=ready,
            provider_identity_verified=ready,
            dry_run=True,
        )
    )


def test_ready_provider_is_registered_without_external_call() -> None:
    _runtime()
    result = _provider()
    assert result['state'] == 'telegram-provider-registered'
    assert result['provider']['provider_ready'] is True
    assert result['provider_api_calls_made'] == 0
    assert result['webhook_registration_performed'] is False
    assert result['external_calls_made'] == 0


def test_provider_registration_requires_enabled_runtime() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.292/register', json={
        'actor': 'brano',
        'webhook_registration_confirmed': True,
        'provider_identity_verified': True,
        'dry_run': True,
    })
    assert response.status_code == 409


def test_same_provider_registration_is_idempotent() -> None:
    _runtime()
    first = _provider()
    replay = _provider()
    assert replay['state'] == 'telegram-provider-already-registered'
    assert replay['idempotent_replay'] is True
    assert replay['provider']['provider_id'] == first['provider']['provider_id']


def test_outbound_reply_is_prepared_but_not_sent() -> None:
    _bind()
    _runtime()
    _provider()
    result = provider.prepare_telegram_outbound(
        provider.TelegramOutboundPrepareRequest(
            telegram_chat_id='1001',
            correlation_id='conversation-292',
            text='AURON ist bereit.',
            reply_to_message_id='message-1',
            dry_run=True,
        )
    )
    assert result['state'] == 'telegram-outbound-prepared'
    assert result['outbound']['delivery_state'] == 'prepared-not-sent'
    assert result['outbound']['provider_call_performed'] is False
    assert result['outbound']['message_sent'] is False
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_outbound_preparation_is_idempotent() -> None:
    _bind()
    _runtime()
    _provider()
    payload = provider.TelegramOutboundPrepareRequest(
        telegram_chat_id='1001', correlation_id='same-292', text='Status', dry_run=True
    )
    first = provider.prepare_telegram_outbound(payload)
    replay = provider.prepare_telegram_outbound(payload)
    assert replay['state'] == 'telegram-outbound-already-prepared'
    assert replay['idempotent_replay'] is True
    assert replay['outbound']['outbound_id'] == first['outbound']['outbound_id']


def test_live_delivery_is_blocked() -> None:
    _bind()
    _runtime()
    _provider()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.292/prepare-outbound', json={
        'telegram_chat_id': '1001',
        'correlation_id': 'live-292',
        'text': 'test',
        'dry_run': False,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.292/command-center')
    assert response.status_code == 200
    assert 'v21.292' in response.text
    assert 'AURON TELEGRAM PROVIDER REGISTRATION COMMAND CENTER' in response.text
