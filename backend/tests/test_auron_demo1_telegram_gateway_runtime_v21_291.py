from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_gateway_runtime_v21_291 as gateway
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()
    gateway.reset_telegram_gateway_runtime_store()


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


def _configure(enabled: bool = True) -> dict:
    return gateway.configure_telegram_runtime(
        gateway.TelegramRuntimeConfigureRequest(
            actor='brano',
            bot_token='1234567890:abcdefghijklmnopqrstuvwxyz',
            webhook_base_url='https://auron.example.com',
            webhook_secret='telegram-webhook-secret-291',
            mode='webhook',
            enabled=enabled,
        )
    )


def test_runtime_configuration_hashes_credentials_and_makes_no_external_call() -> None:
    result = _configure()
    runtime = result['runtime']
    assert result['state'] == 'telegram-runtime-configured'
    assert runtime['credentials_stored_in_plaintext'] is False
    assert runtime['bot_token_digest'] != '1234567890:abcdefghijklmnopqrstuvwxyz'
    assert runtime['webhook_secret_digest'] != 'telegram-webhook-secret-291'
    assert result['telegram_api_calls_made'] == 0
    assert result['webhook_registration_performed'] is False
    assert result['external_calls_made'] == 0


def test_same_runtime_configuration_is_idempotent() -> None:
    first = _configure()
    replay = _configure()
    assert replay['state'] == 'telegram-runtime-already-configured'
    assert replay['idempotent_replay'] is True
    assert replay['runtime']['runtime_id'] == first['runtime']['runtime_id']


def test_verified_webhook_update_enters_existing_bridge() -> None:
    _bind()
    runtime = _configure()['runtime']
    result = gateway.receive_telegram_webhook(
        runtime['runtime_id'],
        gateway.TelegramWebhookUpdateRequest(
            secret_token='telegram-webhook-secret-291',
            update_id='update-291',
            telegram_chat_id='1001',
            telegram_user_id='2001',
            message_id='message-291',
            text='Auron, was ist der Status?',
        ),
    )
    assert result['state'] == 'telegram-webhook-update-accepted'
    assert result['bridge_result']['state'] == 'telegram-message-ingested'
    assert result['gateway_record']['media_type'] == 'text'
    assert result['next_layer'] == 'telegram-text-conversation-routing'
    assert result['external_calls_made'] == 0


def test_webhook_secret_mismatch_is_forbidden() -> None:
    _bind()
    runtime = _configure()['runtime']
    client = TestClient(app)
    response = client.post(
        f"/auron/demo1/v21.291/webhook/{runtime['runtime_id']}",
        json={
            'secret_token': 'wrong-secret',
            'update_id': 'update-x',
            'telegram_chat_id': '1001',
            'telegram_user_id': '2001',
            'message_id': 'message-x',
            'text': 'test',
        },
    )
    assert response.status_code == 403


def test_duplicate_webhook_update_is_idempotent() -> None:
    _bind()
    runtime = _configure()['runtime']
    payload = gateway.TelegramWebhookUpdateRequest(
        secret_token='telegram-webhook-secret-291',
        update_id='update-repeat',
        telegram_chat_id='1001',
        telegram_user_id='2001',
        message_id='message-repeat',
        text='test',
    )
    gateway.receive_telegram_webhook(runtime['runtime_id'], payload)
    replay = gateway.receive_telegram_webhook(runtime['runtime_id'], payload)
    assert replay['state'] == 'telegram-webhook-update-already-processed'
    assert replay['idempotent_replay'] is True


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.291/command-center')
    assert response.status_code == 200
    assert 'v21.291' in response.text
    assert 'AURON TELEGRAM GATEWAY RUNTIME COMMAND CENTER' in response.text
