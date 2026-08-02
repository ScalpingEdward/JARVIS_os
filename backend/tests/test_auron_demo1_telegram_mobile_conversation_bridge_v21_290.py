from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.main import app


def setup_function() -> None:
    bridge.reset_telegram_bridge_store()


def _bind() -> dict:
    return bridge.bind_telegram_chat(
        bridge.TelegramBindRequest(
            actor='brano', telegram_chat_id='chat-1', telegram_user_id='user-1',
            operator_id='brano', workspace_id='demo', pairing_code_verified=True,
        )
    )


def test_verified_pairing_binds_chat_without_external_call() -> None:
    result = _bind()
    assert result['state'] == 'telegram-chat-bound'
    assert result['binding']['active'] is True
    assert result['external_calls_made'] == 0
    assert result['next_layer'] == 'telegram-webhook-adapter'


def test_unverified_pairing_is_rejected() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.290/bind', json={
        'actor': 'brano', 'telegram_chat_id': 'chat-1', 'telegram_user_id': 'user-1',
        'operator_id': 'brano', 'workspace_id': 'demo', 'pairing_code_verified': False,
    })
    assert response.status_code == 403


def test_paired_text_message_is_ingested_idempotently() -> None:
    _bind()
    payload = bridge.TelegramInboundRequest(
        update_id='update-1', telegram_chat_id='chat-1', telegram_user_id='user-1',
        message_id='message-1', text='Auron, was ist mein Status?'
    )
    first = bridge.ingest_telegram_message(payload)
    replay = bridge.ingest_telegram_message(payload)
    assert first['message']['media_type'] == 'text'
    assert first['message']['conversation_routed'] is False
    assert replay['idempotent_replay'] is True
    assert replay['message']['update_id'] == first['message']['update_id']


def test_voice_message_is_prepared_for_transcription() -> None:
    _bind()
    result = bridge.ingest_telegram_message(bridge.TelegramInboundRequest(
        update_id='update-voice', telegram_chat_id='chat-1', telegram_user_id='user-1',
        message_id='message-voice', voice_file_id='telegram-file-1'
    ))
    assert result['message']['media_type'] == 'voice'
    assert result['message']['voice_transcribed'] is False
    assert result['next_layer'] == 'telegram-voice-download-and-transcription'
    assert result['external_calls_made'] == 0


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.290/command-center')
    assert response.status_code == 200
    assert 'v21.290' in response.text
    assert 'AURON TELEGRAM MOBILE CONVERSATION BRIDGE COMMAND CENTER' in response.text
