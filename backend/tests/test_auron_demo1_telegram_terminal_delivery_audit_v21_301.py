from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_delivery_state_commit_v21_296 as original_commit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.api.routes import auron_demo1_telegram_retry_delivery_state_commit_v21_300 as retry_commit
from app.api.routes import auron_demo1_telegram_terminal_delivery_audit_v21_301 as audit
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    original_commit.reset_telegram_delivery_state_commit_store()
    retry_commit.reset_telegram_retry_delivery_state_commit_store()
    audit.reset_telegram_terminal_delivery_audit_store()


def _terminal_chain(state: str = 'delivered', with_retry: bool = True) -> str:
    correlation_id = 'correlation-301'
    original_commit._commit_store[correlation_id] = {
        'commit_id': 'commit-301',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled' if with_retry else state,
        'terminal': False if with_retry else True,
        'attempt': 1,
        'max_attempts': 3,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-301',
        'correlation_id': correlation_id,
        'delivery_state': state,
    }
    if with_retry:
        retry_commit._retry_delivery_commit_store['retry-dispatch-301'] = {
            'retry_delivery_commit_id': 'retry-delivery-commit-301',
            'retry_dispatch_id': 'retry-dispatch-301',
            'retry_receipt_id': 'retry-receipt-301',
            'retry_call_id': 'retry-call-301',
            'retry_id': 'retry-301',
            'correlation_id': correlation_id,
            'delivery_commit_id': 'commit-301',
            'outbound_id': 'outbound-301',
            'provider_message_id': 'telegram-message-301' if state == 'delivered' else None,
            'provider_error': None if state == 'delivered' else 'chat not found',
            'rejection_class': None if state == 'delivered' else 'permanent',
            'attempt': 2,
            'max_attempts': 3,
            'delivery_state': state,
            'terminal': True,
            'committed_by': 'brano',
            'committed_at': '2026-08-02T12:45:00+00:00',
        }
    return correlation_id


def test_terminal_retry_delivery_creates_immutable_audit() -> None:
    correlation_id = _terminal_chain('delivered')
    result = audit.audit_terminal_delivery(audit.TelegramTerminalAuditRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-terminal-delivery-audited'
    assert result['audit']['delivery_state'] == 'delivered'
    assert result['audit']['immutable'] is True
    assert result['audit']['integrity_verified'] is True
    assert len(result['audit']['integrity_hash']) == 64
    assert result['next_layer'] == 'telegram-lifecycle-closure'
    assert result['external_calls_made'] == 0


def test_original_terminal_failure_can_be_audited_without_retry() -> None:
    correlation_id = _terminal_chain('permanent-failure', with_retry=False)
    result = audit.audit_terminal_delivery(audit.TelegramTerminalAuditRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['audit']['delivery_state'] == 'permanent-failure'
    assert result['audit']['retry_delivery_commit_id'] is None


def test_terminal_audit_is_idempotent() -> None:
    correlation_id = _terminal_chain('retry-exhausted')
    payload = audit.TelegramTerminalAuditRequest(correlation_id=correlation_id, actor='brano')
    first = audit.audit_terminal_delivery(payload)
    replay = audit.audit_terminal_delivery(payload)
    assert replay['idempotent_replay'] is True
    assert replay['audit']['audit_id'] == first['audit']['audit_id']
    assert replay['audit']['integrity_hash'] == first['audit']['integrity_hash']


def test_non_terminal_delivery_is_rejected() -> None:
    correlation_id = 'non-terminal-301'
    original_commit._commit_store[correlation_id] = {
        'commit_id': 'commit-non-terminal-301',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled',
        'terminal': False,
        'attempt': 1,
        'max_attempts': 3,
    }
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-non-terminal-301',
        'correlation_id': correlation_id,
        'delivery_state': 'retry-scheduled',
    }
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.301/audit', json={
        'correlation_id': correlation_id, 'actor': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.301/command-center')
    assert response.status_code == 200
    assert 'v21.301' in response.text
    assert 'AURON TELEGRAM TERMINAL DELIVERY AUDIT COMMAND CENTER' in response.text
