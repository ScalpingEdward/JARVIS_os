from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.api.routes import auron_demo1_telegram_correlated_response_controlled_execution_v21_317 as execution
from app.api.routes import auron_demo1_telegram_correlated_response_delivery_admission_v21_316 as admission
from app.api.routes import auron_demo1_telegram_inbound_conversation_dispatch_v21_315 as dispatch
from app.api.routes import auron_demo1_telegram_inbound_lifecycle_closure_audit_v21_319 as closure
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_runtime_result_correlation_v21_318 as result
from app.main import app


def setup_function() -> None:
    closure.reset_telegram_inbound_lifecycle_closure_audit_store()
    execution._execution_handoff_store.clear()
    admission._admission_store.clear()
    dispatch._dispatch_store.clear()
    bridge._message_store.clear()
    provider._outbound_store.clear()
    result._result_commit_store.clear()


def _seed(state: str = 'delivered') -> None:
    delivered = state == 'delivered'
    execution._execution_handoff_store['319'] = {'handoff_id': 'handoff-319', 'execution_id': 'exec-319', 'handoff_state': 'runtime-result-correlated'}
    admission._admission_store['319'] = {'admission_id': 'admission-319', 'execution_id': 'exec-319', 'admission_state': state}
    dispatch._dispatch_store['319'] = {
        'dispatch_id': 'dispatch-319', 'conversation_id': 'conversation-319',
        'correlation_id': 'correlation-319', 'outbound_id': 'outbound-319',
        'live_execution_id': 'exec-319', 'telegram_chat_id': '1001',
        'dispatch_state': state, 'reply_sent': delivered,
        'provider_message_id': 'message-319' if delivered else None,
    }
    bridge._message_store['319'] = {
        'update_id': '319', 'delivery_state': state, 'reply_sent': delivered,
        'provider_message_id': 'message-319' if delivered else None,
    }
    provider._outbound_store['correlation-319'] = {
        'outbound_id': 'outbound-319', 'correlation_id': 'correlation-319',
        'telegram_chat_id': '1001', 'live_execution_id': 'exec-319',
        'delivery_state': state, 'message_sent': delivered,
        'provider_message_id': 'message-319' if delivered else None,
    }
    result._result_commit_store['319'] = {
        'result_commit_id': 'commit-319', 'update_id': '319',
        'execution_id': 'exec-319', 'worker_run_id': 'run-319',
        'receipt_id': 'receipt-319', 'handoff_id': 'handoff-319',
        'admission_id': 'admission-319', 'dispatch_id': 'dispatch-319',
        'correlation_id': 'correlation-319', 'outbound_id': 'outbound-319',
        'delivery_state': state, 'provider_message_id': 'message-319' if delivered else None,
        'provider_error': None if delivered else 'blocked', 'http_status': 200 if delivered else 400,
    }


def test_delivered_lifecycle_is_closed_with_immutable_hash() -> None:
    _seed()
    response = closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319'))
    record = response['closure']
    assert response['state'] == 'telegram-inbound-lifecycle-closed-and-audited'
    assert record['terminal_state'] == 'delivered'
    assert record['immutable'] is True
    assert record['chain_complete'] is True
    assert len(record['integrity_hash']) == 64
    assert dispatch._dispatch_store['319']['dispatch_state'] == 'delivered-closed'


def test_closure_is_idempotent() -> None:
    _seed()
    first = closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319'))
    replay = closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319'))
    assert replay['idempotent_replay'] is True
    assert replay['closure']['closure_id'] == first['closure']['closure_id']


def test_retry_required_is_not_terminal() -> None:
    _seed('retry-required')
    with pytest.raises(HTTPException) as exc:
        closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319'))
    assert exc.value.status_code == 409


def test_inconsistent_chain_is_rejected() -> None:
    _seed()
    provider._outbound_store['correlation-319']['outbound_id'] = 'tampered'
    with pytest.raises(HTTPException) as exc:
        closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319'))
    assert exc.value.status_code == 409


def test_permanent_failure_can_be_closed() -> None:
    _seed('permanent-failure')
    response = closure.close_inbound_lifecycle(closure.TelegramInboundLifecycleClosureRequest(actor='brano', update_id='319', archive=False))
    assert response['closure']['terminal_state'] == 'permanent-failure'
    assert response['closure']['archived'] is False


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.319/command-center')
    assert response.status_code == 200
    assert 'v21.319' in response.text
    assert 'AURON TELEGRAM INBOUND LIFECYCLE CLOSURE AUDIT COMMAND CENTER' in response.text
