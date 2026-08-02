from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as original_commit
from app.api.routes import auron_demo1_telegram_lifecycle_closure_v21_302 as closure
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_retry_delivery_state_commit_v21_300 as retry_commit
from app.api.routes import auron_demo1_telegram_terminal_delivery_audit_v21_301 as audit
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    original_commit.reset_telegram_delivery_state_commit_store()
    retry_commit.reset_telegram_retry_delivery_state_commit_store()
    audit.reset_telegram_terminal_delivery_audit_store()
    closure.reset_telegram_lifecycle_closure_store()


def _audited_chain(state: str = 'delivered', with_retry: bool = True) -> str:
    correlation_id = 'correlation-302'
    original_commit._commit_store[correlation_id] = {
        'commit_id': 'commit-302',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled' if with_retry else state,
        'terminal': False if with_retry else True,
        'attempt': 1,
        'max_attempts': 3,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-302',
        'correlation_id': correlation_id,
        'delivery_state': state,
    }
    retry_delivery_commit_id = None
    if with_retry:
        retry_delivery_commit_id = 'retry-delivery-commit-302'
        retry_commit._retry_delivery_commit_store['retry-dispatch-302'] = {
            'retry_delivery_commit_id': retry_delivery_commit_id,
            'retry_dispatch_id': 'retry-dispatch-302',
            'retry_receipt_id': 'retry-receipt-302',
            'retry_call_id': 'retry-call-302',
            'retry_id': 'retry-302',
            'correlation_id': correlation_id,
            'delivery_commit_id': 'commit-302',
            'outbound_id': 'outbound-302',
            'provider_message_id': 'telegram-message-302' if state == 'delivered' else None,
            'provider_error': None if state == 'delivered' else 'chat not found',
            'attempt': 2,
            'max_attempts': 3,
            'delivery_state': state,
            'terminal': True,
            'committed_at': '2026-08-02T12:50:00+00:00',
        }
    audit._audit_store[correlation_id] = {
        'audit_id': 'audit-302',
        'audit_version': 'v21.301',
        'correlation_id': correlation_id,
        'delivery_state': state,
        'original_commit_id': 'commit-302',
        'retry_delivery_commit_id': retry_delivery_commit_id,
        'outbound_id': 'outbound-302',
        'provider_message_id': 'telegram-message-302' if state == 'delivered' else None,
        'attempt': 2 if with_retry else 1,
        'max_attempts': 3,
        'integrity_hash': 'a' * 64,
        'integrity_verified': True,
        'immutable': True,
        'terminal': True,
        'audited_at': '2026-08-02T12:51:00+00:00',
    }
    return correlation_id


def test_audited_terminal_chain_is_closed_and_archived() -> None:
    correlation_id = _audited_chain()
    result = closure.close_telegram_lifecycle(closure.TelegramLifecycleClosureRequest(
        correlation_id=correlation_id, actor='brano', archive=True
    ))
    assert result['state'] == 'telegram-lifecycle-closed'
    assert result['closure']['chain_complete'] is True
    assert result['closure']['lifecycle_closed'] is True
    assert result['closure']['archived'] is True
    assert result['closure']['integrity_hash'] == 'a' * 64
    assert result['next_layer'] == 'telegram-production-transport-activation-gate'
    assert result['external_calls_made'] == 0


def test_original_terminal_chain_closes_without_retry() -> None:
    correlation_id = _audited_chain('permanent-failure', with_retry=False)
    result = closure.close_telegram_lifecycle(closure.TelegramLifecycleClosureRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['closure']['delivery_state'] == 'permanent-failure'
    assert result['closure']['retry_delivery_commit_id'] is None


def test_lifecycle_closure_is_idempotent() -> None:
    correlation_id = _audited_chain('retry-exhausted')
    payload = closure.TelegramLifecycleClosureRequest(correlation_id=correlation_id, actor='brano')
    first = closure.close_telegram_lifecycle(payload)
    replay = closure.close_telegram_lifecycle(payload)
    assert replay['idempotent_replay'] is True
    assert replay['closure']['closure_id'] == first['closure']['closure_id']


def test_integrity_mismatch_blocks_closure() -> None:
    correlation_id = _audited_chain()
    audit._audit_store[correlation_id]['outbound_id'] = 'wrong-outbound'
    result = closure.close_telegram_lifecycle(closure.TelegramLifecycleClosureRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-lifecycle-closure-blocked'
    assert 'audit_outbound_matches' in result['blockers']
    assert result['external_calls_made'] == 0


def test_missing_audit_is_rejected() -> None:
    correlation_id = _audited_chain()
    audit._audit_store.clear()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.302/close', json={
        'correlation_id': correlation_id, 'actor': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.302/command-center')
    assert response.status_code == 200
    assert 'v21.302' in response.text
    assert 'AURON TELEGRAM LIFECYCLE CLOSURE COMMAND CENTER' in response.text
