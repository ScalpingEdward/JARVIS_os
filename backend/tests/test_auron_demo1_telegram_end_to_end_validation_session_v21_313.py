from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_end_to_end_validation_session_v21_313 as e2e
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_secure_bot_provisioning_v21_312 as provisioning
from app.main import app


def setup_function() -> None:
    e2e.reset_telegram_end_to_end_validation_session_store()
    bridge.reset_telegram_bridge_store()
    provisioning.reset_telegram_secure_bot_provisioning_store()


def _ready_state() -> None:
    provisioning._validation_store['fingerprint-313'] = {
        'token_fingerprint': 'fingerprint-313',
        'bot_id': '123456789',
        'runtime_ready': True,
    }
    bridge._binding_store['1001'] = {
        'binding_id': 'binding-313',
        'operator_id': 'brano',
        'telegram_chat_id': '1001',
        'telegram_user_id': 'user-313',
        'workspace_id': 'jarvis-os',
        'active': True,
    }


def _start_payload() -> e2e.TelegramEndToEndValidationStartRequest:
    return e2e.TelegramEndToEndValidationStartRequest(
        actor='brano',
        workspace_id='jarvis-os',
        operator_id='brano',
        telegram_chat_id='1001',
        test_message='Hallo AURON E2E 313',
        approval_phrase='START ONE AURON TELEGRAM END TO END VALIDATION',
    )


def test_ready_session_starts_without_external_call() -> None:
    _ready_state()
    result = e2e.start_validation_session(_start_payload())
    assert result['state'] == 'telegram-end-to-end-validation-started'
    assert result['session']['state'] == 'awaiting-evidence'
    assert result['session']['bot_id'] == '123456789'
    assert result['session']['pairing_id'] == 'binding-313'
    assert result['external_calls_made'] == 0


def test_start_is_idempotent() -> None:
    _ready_state()
    payload = _start_payload()
    first = e2e.start_validation_session(payload)
    replay = e2e.start_validation_session(payload)
    assert replay['idempotent_replay'] is True
    assert replay['session']['session_id'] == first['session']['session_id']


def test_missing_readiness_blocks_session() -> None:
    result = e2e.start_validation_session(_start_payload())
    assert result['state'] == 'telegram-end-to-end-validation-blocked'
    assert 'runtime_provisioning_validated' in result['blockers']
    assert 'operator_chat_paired' in result['blockers']


def test_complete_passes_only_with_full_evidence() -> None:
    _ready_state()
    started = e2e.start_validation_session(_start_payload())
    result = e2e.complete_validation_session(e2e.TelegramEndToEndValidationCompleteRequest(
        session_id=started['session']['session_id'],
        inbound_received=True,
        conversation_routed=True,
        outbound_prepared=True,
        provider_call_completed=True,
        phone_reply_observed=True,
        correlation_id='correlation-313',
        provider_message_id='message-313',
    ))
    assert result['state'] == 'telegram-end-to-end-validation-passed'
    assert result['session']['chain_complete'] is True
    assert result['next_layer'] == 'telegram-inbound-webhook-processing'


def test_incomplete_evidence_fails_validation() -> None:
    _ready_state()
    started = e2e.start_validation_session(_start_payload())
    result = e2e.complete_validation_session(e2e.TelegramEndToEndValidationCompleteRequest(
        session_id=started['session']['session_id'],
        inbound_received=True,
        conversation_routed=True,
        outbound_prepared=True,
        provider_call_completed=False,
        phone_reply_observed=False,
    ))
    assert result['state'] == 'telegram-end-to-end-validation-failed'
    assert result['session']['chain_complete'] is False


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.313/command-center')
    assert response.status_code == 200
    assert 'v21.313' in response.text
    assert 'AURON TELEGRAM END TO END VALIDATION COMMAND CENTER' in response.text
