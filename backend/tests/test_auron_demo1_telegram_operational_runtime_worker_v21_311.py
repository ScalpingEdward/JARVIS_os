from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_controlled_live_transport_adapter_v21_304 as live
from app.api.routes import auron_demo1_telegram_operational_runtime_worker_v21_311 as worker
from app.main import app


def setup_function() -> None:
    live.reset_telegram_controlled_live_transport_adapter_store()
    worker.reset_telegram_operational_runtime_worker_store()


def _execution() -> str:
    execution_id = 'execution-311'
    live._live_execution_store['correlation-311'] = {
        'execution_id': execution_id,
        'correlation_id': 'correlation-311',
        'execution_state': 'authorized-awaiting-runtime-worker',
        'request_body': {'chat_id': '1001', 'text': 'Hallo von AURON'},
    }
    return execution_id


def _payload(execution_id: str) -> worker.TelegramRuntimeWorkerRequest:
    return worker.TelegramRuntimeWorkerRequest(
        execution_id=execution_id,
        actor='brano',
        execution_phrase='RUN ONE AURON TELEGRAM PROVIDER CALL',
    )


def test_successful_provider_call_creates_receipt_and_worker_run() -> None:
    execution_id = _execution()

    def fake_transport(token: str, request_body: dict, timeout: int):
        assert request_body['chat_id'] == '1001'
        return 200, {'ok': True, 'result': {'message_id': 311}}

    result = worker.execute_runtime_worker(_payload(execution_id), transport=fake_transport)
    assert result['state'] == 'telegram-runtime-worker-call-completed'
    assert result['run']['accepted'] is True
    assert result['run']['provider_message_id'] == '311'
    assert result['run']['telegram_api_calls_made'] == 1
    assert result['run']['outbound_messages_sent'] == 1
    assert live._live_receipt_store[execution_id]['accepted'] is True
    assert result['next_layer'] == 'telegram-live-delivery-state-commit'


def test_rejected_provider_call_is_captured() -> None:
    execution_id = _execution()

    def fake_transport(token: str, request_body: dict, timeout: int):
        return 400, {'ok': False, 'description': 'chat not found'}

    result = worker.execute_runtime_worker(_payload(execution_id), transport=fake_transport)
    assert result['run']['accepted'] is False
    assert result['run']['provider_error'] == 'chat not found'
    assert result['run']['outbound_messages_sent'] == 0
    assert live._live_receipt_store[execution_id]['accepted'] is False


def test_worker_execution_is_idempotent() -> None:
    execution_id = _execution()

    def fake_transport(token: str, request_body: dict, timeout: int):
        return 200, {'ok': True, 'result': {'message_id': 311}}

    first = worker.execute_runtime_worker(_payload(execution_id), transport=fake_transport)
    replay = worker.execute_runtime_worker(_payload(execution_id), transport=fake_transport)
    assert replay['idempotent_replay'] is True
    assert replay['run']['worker_run_id'] == first['run']['worker_run_id']


def test_disabled_worker_route_is_blocked(monkeypatch) -> None:
    execution_id = _execution()
    monkeypatch.delenv('TELEGRAM_RUNTIME_WORKER_ENABLED', raising=False)
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.311/execute', json=_payload(execution_id).model_dump())
    assert response.status_code == 409


def test_wrong_execution_phrase_is_rejected() -> None:
    execution_id = _execution()
    client = TestClient(app)
    payload = _payload(execution_id).model_dump()
    payload['execution_phrase'] = 'wrong phrase'
    response = client.post('/auron/demo1/v21.311/execute', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.311/command-center')
    assert response.status_code == 200
    assert 'v21.311' in response.text
    assert 'AURON TELEGRAM OPERATIONAL RUNTIME WORKER COMMAND CENTER' in response.text
