from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_correlated_response_delivery_admission_v21_316 as admission
from app.api.routes import auron_demo1_telegram_inbound_conversation_dispatch_v21_315 as dispatch
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_production_activation_gate_v21_303 as activation
from app.main import app


def setup_function() -> None:
    admission.reset_telegram_correlated_response_delivery_admission_store()
    dispatch._dispatch_store.clear()
    provider._outbound_store.clear()
    activation._activation_store.clear()
    dispatch._dispatch_store['316001'] = {
        'dispatch_id': 'dispatch-316', 'conversation_id': 'conversation-316', 'correlation_id': 'correlation-316',
        'outbound_id': 'outbound-316', 'telegram_chat_id': '1001', 'operator_id': 'brano', 'workspace_id': 'jarvis-os',
        'response_text': 'Antwort 316', 'dispatch_state': 'response-correlated-awaiting-controlled-delivery', 'reply_sent': False,
    }
    provider._outbound_store['correlation-316'] = {
        'outbound_id': 'outbound-316', 'correlation_id': 'correlation-316', 'provider_id': 'provider-316', 'runtime_id': 'runtime-316',
        'telegram_chat_id': '1001', 'operator_id': 'brano', 'workspace_id': 'jarvis-os', 'text': 'Antwort 316',
        'reply_to_message_id': '77', 'delivery_state': 'prepared-not-sent', 'message_sent': False,
    }
    activation._activation_store['active-316'] = {
        'activation_id': 'activation-316', 'provider_id': 'provider-316', 'runtime_id': 'runtime-316',
        'active': True, 'production_transport_authorized': True,
    }


def _payload() -> admission.TelegramCorrelatedResponseAdmissionRequest:
    return admission.TelegramCorrelatedResponseAdmissionRequest(actor='brano', update_id='316001', approval_phrase='ADMIT ONE AURON TELEGRAM CORRELATED RESPONSE')


def test_correlated_response_is_admitted_without_external_call() -> None:
    result = admission.admit_correlated_response(_payload())
    assert result['state'] == 'telegram-correlated-response-delivery-admitted'
    assert result['admission']['admission_state'] == 'authorized-awaiting-controlled-execution-handoff'
    assert result['external_calls_made'] == 0
    assert dispatch._dispatch_store['316001']['admission_id'] == result['admission']['admission_id']
    assert provider._outbound_store['correlation-316']['delivery_state'] == 'delivery-admitted-not-sent'


def test_admission_is_idempotent() -> None:
    first = admission.admit_correlated_response(_payload())
    replay = admission.admit_correlated_response(_payload())
    assert replay['idempotent_replay'] is True
    assert replay['admission']['admission_id'] == first['admission']['admission_id']


def test_missing_activation_fails_closed() -> None:
    activation._activation_store.clear()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.316/admit', json=_payload().model_dump())
    assert response.status_code == 409


def test_mismatched_outbound_is_rejected() -> None:
    provider._outbound_store['correlation-316']['text'] = 'tampered'
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.316/admit', json=_payload().model_dump())
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.316/command-center')
    assert response.status_code == 200
    assert 'v21.316' in response.text
    assert 'AURON TELEGRAM CORRELATED RESPONSE DELIVERY ADMISSION COMMAND CENTER' in response.text
