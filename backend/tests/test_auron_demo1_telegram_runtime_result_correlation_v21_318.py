from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_correlated_response_controlled_execution_v21_317 as execution
from app.api.routes import auron_demo1_telegram_correlated_response_delivery_admission_v21_316 as admission
from app.api.routes import auron_demo1_telegram_inbound_conversation_dispatch_v21_315 as dispatch
from app.api.routes import auron_demo1_telegram_mobile_conversation_bridge_v21_290 as bridge
from app.api.routes import auron_demo1_telegram_operational_runtime_worker_v21_311 as worker
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_runtime_result_correlation_v21_318 as correlation
from app.main import app


def setup_function() -> None:
    correlation.reset_telegram_runtime_result_correlation_store()
    execution.reset_telegram_correlated_response_controlled_execution_store()
    admission.reset_telegram_correlated_response_delivery_admission_store()
    dispatch.reset_telegram_inbound_conversation_dispatch_store()
    bridge.reset_telegram_bridge_store()
    provider.reset_telegram_provider_registration_store()
    worker.reset_telegram_operational_runtime_worker_store()


def _ready(accepted: bool = True, http_status: int = 200) -> None:
    update_id = '318001'
    execution_id = 'execution-318'
    correlation_id = 'correlation-318'
    bridge._message_store[update_id] = {'update_id': update_id, 'reply_sent': False}
    dispatch._dispatch_store[update_id] = {
        'dispatch_id': 'dispatch-318', 'conversation_id': 'conversation-318',
        'correlation_id': correlation_id, 'outbound_id': 'outbound-318',
        'telegram_chat_id': '1001', 'live_execution_id': execution_id,
        'dispatch_state': 'execution-contract-prepared-awaiting-runtime-worker', 'reply_sent': False,
    }
    admission._admission_store[update_id] = {
        'admission_id': 'admission-318', 'execution_id': execution_id,
        'admission_state': 'execution-contract-prepared-awaiting-runtime-worker',
    }
    execution._execution_handoff_store[update_id] = {
        'handoff_id': 'handoff-318', 'execution_id': execution_id,
        'handoff_state': 'runtime-worker-ready', 'prepared_at': '2026-08-02T00:00:00+00:00',
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-318', 'telegram_chat_id': '1001',
        'live_execution_id': execution_id, 'delivery_state': 'execution-contract-prepared-not-sent',
        'message_sent': False,
    }
    worker._worker_run_store[execution_id] = {
        'worker_run_id': 'worker-run-318', 'execution_id': execution_id,
        'correlation_id': correlation_id, 'receipt_id': 'receipt-318',
        'accepted': accepted, 'http_status': http_status,
        'provider_message_id': '9001' if accepted else None,
        'provider_error': None if accepted else ('network timeout' if http_status >= 500 else 'chat not found'),
    }


def _payload() -> correlation.TelegramRuntimeResultCorrelationRequest:
    return correlation.TelegramRuntimeResultCorrelationRequest(actor='brano', update_id='318001', execution_id='execution-318')


def test_successful_runtime_result_closes_reply_delivery() -> None:
    _ready()
    result = correlation.commit_runtime_result(_payload())
    assert result['commit']['delivery_state'] == 'delivered'
    assert dispatch._dispatch_store['318001']['reply_sent'] is True
    assert provider._outbound_store['correlation-318']['message_sent'] is True
    assert bridge._message_store['318001']['provider_message_id'] == '9001'
    assert result['external_calls_made'] == 0


def test_transient_failure_requires_retry() -> None:
    _ready(accepted=False, http_status=503)
    result = correlation.commit_runtime_result(_payload())
    assert result['commit']['delivery_state'] == 'retry-required'
    assert dispatch._dispatch_store['318001']['reply_sent'] is False
    assert result['next_layer'] == 'telegram-correlated-response-retry-or-failure-handling'


def test_permanent_failure_is_classified() -> None:
    _ready(accepted=False, http_status=400)
    result = correlation.commit_runtime_result(_payload())
    assert result['commit']['delivery_state'] == 'permanent-failure'


def test_commit_is_idempotent() -> None:
    _ready()
    first = correlation.commit_runtime_result(_payload())
    replay = correlation.commit_runtime_result(_payload())
    assert replay['idempotent_replay'] is True
    assert replay['commit']['result_commit_id'] == first['commit']['result_commit_id']


def test_mismatched_execution_is_blocked() -> None:
    _ready()
    worker._worker_run_store['wrong'] = dict(worker._worker_run_store['execution-318'], execution_id='wrong')
    try:
        correlation.commit_runtime_result(correlation.TelegramRuntimeResultCorrelationRequest(actor='brano', update_id='318001', execution_id='wrong'))
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Expected correlation mismatch to be rejected')


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.318/command-center')
    assert response.status_code == 200
    assert 'v21.318' in response.text
    assert 'AURON TELEGRAM RUNTIME RESULT CORRELATION COMMAND CENTER' in response.text
