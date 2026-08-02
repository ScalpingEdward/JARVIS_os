from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_live_transport_adapter_v21_304 as live
from app.api.routes import auron_demo1_telegram_controlled_send_adapter_v21_294 as send
from app.api.routes import auron_demo1_telegram_production_activation_gate_v21_303 as gate
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    send.reset_telegram_controlled_send_store()
    gate.reset_telegram_production_activation_gate_store()
    live.reset_telegram_controlled_live_transport_adapter_store()


def _ready_chain() -> str:
    correlation_id = 'correlation-304'
    provider._provider_store['provider-304'] = {
        'provider_id': 'provider-304', 'runtime_id': 'runtime-304',
        'provider_ready': True, 'active': True,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-304', 'correlation_id': correlation_id,
        'provider_id': 'provider-304', 'runtime_id': 'runtime-304',
        'telegram_chat_id': '1001', 'text': 'Hallo von AURON',
        'reply_to_message_id': 'message-304', 'parse_mode': None,
        'disable_notification': False, 'delivery_state': 'dispatch-prepared',
    }
    send._dispatch_store[correlation_id] = {
        'dispatch_id': 'dispatch-304', 'correlation_id': correlation_id,
        'outbound_id': 'outbound-304', 'provider_id': 'provider-304',
        'runtime_id': 'runtime-304', 'dispatch_state': 'prepared-not-called',
    }
    gate._activation_store['runtime-304:provider-304:brano'] = {
        'activation_id': 'activation-304', 'runtime_id': 'runtime-304',
        'provider_id': 'provider-304', 'production_transport_authorized': True,
        'active': True,
    }
    return correlation_id


def _payload(correlation_id: str, **overrides):
    values = {
        'correlation_id': correlation_id,
        'actor': 'brano',
        'execution_phrase': 'EXECUTE ONE AURON TELEGRAM MESSAGE',
        'credentials_loaded_in_runtime': True,
        'network_egress_available': True,
        'execute_provider_call': False,
    }
    values.update(overrides)
    return live.TelegramLiveExecutionRequest(**values)


def test_authorized_single_message_execution_contract_is_prepared() -> None:
    correlation_id = _ready_chain()
    result = live.prepare_live_execution(_payload(correlation_id))
    assert result['state'] == 'telegram-live-execution-contract-prepared'
    assert result['execution']['method'] == 'sendMessage'
    assert result['execution']['dispatch_id'] == 'dispatch-304'
    assert result['execution']['provider_call_performed'] is False
    assert result['telegram_api_calls_made'] == 0
    assert result['outbound_messages_sent'] == 0
    assert result['external_calls_made'] == 0


def test_live_execution_contract_is_idempotent() -> None:
    correlation_id = _ready_chain()
    payload = _payload(correlation_id)
    first = live.prepare_live_execution(payload)
    replay = live.prepare_live_execution(payload)
    assert replay['idempotent_replay'] is True
    assert replay['execution']['execution_id'] == first['execution']['execution_id']


def test_missing_runtime_readiness_blocks_execution() -> None:
    correlation_id = _ready_chain()
    result = live.prepare_live_execution(_payload(correlation_id, network_egress_available=False))
    assert result['state'] == 'telegram-live-execution-blocked'
    assert 'network_egress_available' in result['blockers']


def test_accepted_provider_receipt_is_captured() -> None:
    correlation_id = _ready_chain()
    prepared = live.prepare_live_execution(_payload(correlation_id))
    result = live.capture_live_provider_receipt(live.TelegramLiveReceiptRequest(
        execution_id=prepared['execution']['execution_id'], accepted=True,
        provider_message_id='telegram-message-304', http_status=200,
    ))
    assert result['state'] == 'telegram-live-provider-receipt-captured'
    assert result['receipt']['verification_state'] == 'accepted-awaiting-delivery-commit'
    assert result['next_layer'] == 'telegram-live-delivery-state-commit'


def test_direct_network_execution_is_rejected() -> None:
    correlation_id = _ready_chain()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.304/prepare-execution', json={
        **_payload(correlation_id).model_dump(), 'execute_provider_call': True,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.304/command-center')
    assert response.status_code == 200
    assert 'v21.304' in response.text
    assert 'AURON TELEGRAM CONTROLLED LIVE TRANSPORT ADAPTER COMMAND CENTER' in response.text
