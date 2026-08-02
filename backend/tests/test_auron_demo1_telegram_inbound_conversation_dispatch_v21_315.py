from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_inbound_conversation_dispatch_v21_315 as dispatch
from app.api.routes import auron_demo1_telegram_inbound_webhook_receiver_v21_314 as webhook
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_conversation_router_v21_293 as conversation
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    dispatch.reset_telegram_inbound_conversation_dispatch_store()
    webhook.reset_telegram_inbound_webhook_receiver_store()
    bridge.reset_telegram_bridge_store()
    conversation.reset_telegram_conversation_router_store()
    provider.reset_telegram_provider_registration_store()
    bridge._binding_store['1001'] = {
        'binding_id': 'binding-315', 'telegram_chat_id': '1001', 'telegram_user_id': '2002',
        'operator_id': 'brano', 'workspace_id': 'jarvis-os', 'active': True,
    }
    bridge._message_store['315001'] = {
        'update_id': '315001', 'message_id': '88', 'telegram_chat_id': '1001',
        'operator_id': 'brano', 'workspace_id': 'jarvis-os', 'media_type': 'text',
        'text': 'AURON Status bitte', 'conversation_routed': False, 'reply_sent': False,
    }
    webhook._webhook_receipt_store['315001'] = {
        'webhook_receipt_id': 'receipt-315', 'update_id': '315001', 'secret_verified': True,
    }
    provider._provider_store['provider-315'] = {
        'provider_id': 'provider-315', 'runtime_id': 'runtime-315', 'active': True, 'provider_ready': True,
    }


def test_verified_message_is_dispatched_and_correlated() -> None:
    result = dispatch.dispatch_inbound_conversation(dispatch.TelegramInboundConversationDispatchRequest(actor='brano', update_id='315001'))
    assert result['state'] == 'telegram-inbound-conversation-dispatched'
    assert result['dispatch']['webhook_receipt_id'] == 'receipt-315'
    assert result['dispatch']['correlation_id']
    assert result['dispatch']['dispatch_state'] == 'response-correlated-awaiting-controlled-delivery'
    assert result['external_calls_made'] == 0


def test_dispatch_is_idempotent() -> None:
    payload = dispatch.TelegramInboundConversationDispatchRequest(actor='brano', update_id='315001')
    first = dispatch.dispatch_inbound_conversation(payload)
    replay = dispatch.dispatch_inbound_conversation(payload)
    assert replay['idempotent_replay'] is True
    assert replay['dispatch']['dispatch_id'] == first['dispatch']['dispatch_id']


def test_unverified_update_is_blocked() -> None:
    webhook._webhook_receipt_store.clear()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.315/dispatch', json={'actor': 'brano', 'update_id': '315001'})
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.315/command-center')
    assert response.status_code == 200
    assert 'v21.315' in response.text
    assert 'AURON TELEGRAM INBOUND CONVERSATION DISPATCH COMMAND CENTER' in response.text
