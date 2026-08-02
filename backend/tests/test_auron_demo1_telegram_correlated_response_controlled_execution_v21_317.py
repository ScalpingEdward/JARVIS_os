from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_correlated_response_controlled_execution_v21_317 as execution
from app.api.routes import auron_demo1_telegram_correlated_response_delivery_admission_v21_316 as admission
from app.api.routes import auron_demo1_telegram_controlled_live_transport_adapter_v21_304 as live
from app.api.routes import auron_demo1_telegram_inbound_conversation_dispatch_v21_315 as dispatch
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    execution.reset_telegram_correlated_response_controlled_execution_store()
    admission.reset_telegram_correlated_response_delivery_admission_store()
    live.reset_telegram_controlled_live_transport_adapter_store()
    dispatch.reset_telegram_inbound_conversation_dispatch_store()
    provider._outbound_store.clear()
    _ready_state()


def _ready_state() -> None:
    admission._admission_store['317001'] = {
        'admission_id': 'admission-317',
        'update_id': '317001',
        'dispatch_id': 'dispatch-317',
        'conversation_id': 'conversation-317',
        'correlation_id': 'correlation-317',
        'outbound_id': 'outbound-317',
        'activation_id': 'activation-317',
        'provider_id': 'provider-317',
        'runtime_id': 'runtime-317',
        'telegram_chat_id': '1001',
        'response_text': 'Hallo vom AURON',
        'admission_state': 'authorized-awaiting-controlled-execution-handoff',
    }
    dispatch._dispatch_store['317001'] = {
        'dispatch_id': 'dispatch-317',
        'admission_id': 'admission-317',
        'dispatch_state': 'delivery-admitted-awaiting-controlled-execution-handoff',
    }
    provider._outbound_store['correlation-317'] = {
        'outbound_id': 'outbound-317',
        'admission_id': 'admission-317',
        'provider_id': 'provider-317',
        'runtime_id': 'runtime-317',
        'telegram_chat_id': '1001',
        'text': 'Hallo vom AURON',
        'reply_to_message_id': '77',
        'parse_mode': None,
        'disable_notification': False,
        'delivery_state': 'delivery-admitted-not-sent',
        'message_sent': False,
    }


def _payload(**overrides) -> execution.TelegramCorrelatedResponseExecutionRequest:
    values = {
        'actor': 'brano',
        'update_id': '317001',
        'execution_phrase': 'PREPARE ONE AURON TELEGRAM CORRELATED RESPONSE EXECUTION',
        'credentials_loaded_in_runtime': True,
        'network_egress_available': True,
    }
    values.update(overrides)
    return execution.TelegramCorrelatedResponseExecutionRequest(**values)


def test_prepares_runtime_worker_execution_contract() -> None:
    result = execution.prepare_correlated_response_execution(_payload())
    assert result['state'] == 'telegram-correlated-response-execution-contract-prepared'
    assert result['execution']['execution_state'] == 'authorized-awaiting-runtime-worker'
    assert result['execution']['request_body']['chat_id'] == '1001'
    assert result['execution']['request_body']['text'] == 'Hallo vom AURON'
    assert result['handoff']['handoff_state'] == 'runtime-worker-ready'
    assert result['external_calls_made'] == 0
    assert live._live_execution_store['correlation-317']['execution_id'] == result['execution']['execution_id']


def test_prepare_is_idempotent() -> None:
    first = execution.prepare_correlated_response_execution(_payload())
    replay = execution.prepare_correlated_response_execution(_payload())
    assert replay['idempotent_replay'] is True
    assert replay['handoff']['execution_id'] == first['handoff']['execution_id']


def test_runtime_readiness_blockers_prevent_handoff() -> None:
    result = execution.prepare_correlated_response_execution(_payload(network_egress_available=False))
    assert result['state'] == 'telegram-correlated-response-execution-blocked'
    assert 'network_egress_available' in result['blockers']
    assert live._live_execution_store == {}


def test_tampered_response_is_blocked() -> None:
    provider._outbound_store['correlation-317']['text'] = 'manipuliert'
    result = execution.prepare_correlated_response_execution(_payload())
    assert result['state'] == 'telegram-correlated-response-execution-blocked'
    assert 'response_text_matches' in result['blockers']


def test_direct_provider_call_is_rejected() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.317/prepare-execution', json={
        'actor': 'brano',
        'update_id': '317001',
        'execution_phrase': 'PREPARE ONE AURON TELEGRAM CORRELATED RESPONSE EXECUTION',
        'credentials_loaded_in_runtime': True,
        'network_egress_available': True,
        'execute_provider_call': True,
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.317/command-center')
    assert response.status_code == 200
    assert 'v21.317' in response.text
    assert 'AURON TELEGRAM CORRELATED RESPONSE CONTROLLED EXECUTION COMMAND CENTER' in response.text
