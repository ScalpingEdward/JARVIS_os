import os

from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_inbound_webhook_receiver_v21_314 as webhook
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.main import app


def setup_function() -> None:
    webhook.reset_telegram_inbound_webhook_receiver_store()
    bridge.reset_telegram_bridge_store()
    os.environ['TELEGRAM_WEBHOOK_SECRET'] = 'secret-314'
    bridge._binding_store['1001'] = {
        'binding_id': 'binding-314',
        'telegram_chat_id': '1001',
        'telegram_user_id': '2002',
        'operator_id': 'brano',
        'workspace_id': 'jarvis-os',
        'active': True,
    }


def teardown_function() -> None:
    os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)


def _payload() -> dict:
    return {
        'update_id': 314001,
        'message': {
            'message_id': 77,
            'from': {'id': 2002},
            'chat': {'id': 1001},
            'text': 'Hallo AURON',
        },
    }


def test_verified_text_update_is_ingested() -> None:
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.314/webhook',
        json=_payload(),
        headers={'X-Telegram-Bot-Api-Secret-Token': 'secret-314'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'telegram-webhook-update-accepted'
    assert body['receipt']['secret_verified'] is True
    assert body['message']['text'] == 'Hallo AURON'
    assert body['external_calls_made'] == 0


def test_invalid_secret_is_rejected() -> None:
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.314/webhook',
        json=_payload(),
        headers={'X-Telegram-Bot-Api-Secret-Token': 'wrong'},
    )
    assert response.status_code == 403


def test_unpaired_sender_is_rejected() -> None:
    bridge._binding_store.clear()
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.314/webhook',
        json=_payload(),
        headers={'X-Telegram-Bot-Api-Secret-Token': 'secret-314'},
    )
    assert response.status_code == 403


def test_duplicate_update_is_idempotent() -> None:
    client = TestClient(app)
    headers = {'X-Telegram-Bot-Api-Secret-Token': 'secret-314'}
    first = client.post('/auron/demo1/v21.314/webhook', json=_payload(), headers=headers)
    replay = client.post('/auron/demo1/v21.314/webhook', json=_payload(), headers=headers)
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()['idempotent_replay'] is True
    assert replay.json()['receipt']['webhook_receipt_id'] == first.json()['receipt']['webhook_receipt_id']


def test_voice_update_is_accepted() -> None:
    payload = _payload()
    payload['update_id'] = 314002
    payload['message'].pop('text')
    payload['message']['voice'] = {'file_id': 'voice-file-314'}
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.314/webhook',
        json=payload,
        headers={'X-Telegram-Bot-Api-Secret-Token': 'secret-314'},
    )
    assert response.status_code == 200
    assert response.json()['receipt']['media_type'] == 'voice'
    assert response.json()['next_layer'] == 'telegram-voice-download-and-transcription'


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.314/command-center')
    assert response.status_code == 200
    assert 'v21.314' in response.text
    assert 'AURON TELEGRAM INBOUND WEBHOOK RECEIVER COMMAND CENTER' in response.text
