from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_live_lifecycle_closure_v21_310 as closure
from app.api.routes import auron_demo1_telegram_live_terminal_delivery_audit_v21_309 as audit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    audit.reset_telegram_live_terminal_delivery_audit_store()
    closure.reset_telegram_live_lifecycle_closure_store()


def _ready_chain() -> str:
    correlation_id = 'correlation-310'
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-310',
        'correlation_id': correlation_id,
        'delivery_state': 'delivered',
        'live_terminal_audit_id': 'audit-310',
        'live_terminal_integrity_hash': 'a' * 64,
    }
    audit._live_terminal_audit_store[correlation_id] = {
        'live_terminal_audit_id': 'audit-310',
        'correlation_id': correlation_id,
        'outbound_id': 'outbound-310',
        'provider_id': 'provider-310',
        'runtime_id': 'runtime-310',
        'final_delivery_state': 'delivered',
        'final_attempt': 2,
        'integrity_hash': 'a' * 64,
        'integrity_verified': True,
        'immutable': True,
        'chain_complete': True,
    }
    return correlation_id


def test_verified_live_lifecycle_is_closed_and_archived() -> None:
    correlation_id = _ready_chain()
    result = closure.close_telegram_live_lifecycle(closure.TelegramLiveLifecycleClosureRequest(
        correlation_id=correlation_id, actor='brano', archive=True
    ))
    assert result['state'] == 'telegram-live-lifecycle-closed'
    assert result['closure']['lifecycle_closed'] is True
    assert result['closure']['archived'] is True
    assert result['closure']['integrity_hash'] == 'a' * 64
    assert result['next_layer'] == 'telegram-operational-runtime-worker-integration'
    assert result['external_calls_made'] == 0


def test_live_lifecycle_closure_is_idempotent() -> None:
    correlation_id = _ready_chain()
    payload = closure.TelegramLiveLifecycleClosureRequest(correlation_id=correlation_id, actor='brano')
    first = closure.close_telegram_live_lifecycle(payload)
    replay = closure.close_telegram_live_lifecycle(payload)
    assert replay['idempotent_replay'] is True
    assert replay['closure']['live_lifecycle_closure_id'] == first['closure']['live_lifecycle_closure_id']


def test_integrity_mismatch_blocks_closure() -> None:
    correlation_id = _ready_chain()
    provider._outbound_store[correlation_id]['live_terminal_integrity_hash'] = 'wrong'
    result = closure.close_telegram_live_lifecycle(closure.TelegramLiveLifecycleClosureRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-live-lifecycle-closure-blocked'
    assert 'outbound_integrity_hash_matches' in result['blockers']


def test_missing_audit_is_rejected() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.310/close', json={
        'correlation_id': 'missing', 'actor': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.310/command-center')
    assert response.status_code == 200
    assert 'v21.310' in response.text
    assert 'AURON TELEGRAM LIVE LIFECYCLE CLOSURE COMMAND CENTER' in response.text
