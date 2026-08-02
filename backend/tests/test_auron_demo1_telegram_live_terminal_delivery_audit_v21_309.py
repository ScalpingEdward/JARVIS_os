from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_telegram_live_delivery_state_commit_v21_305 as original
from app.api.routes import auron_demo1_telegram_live_retry_receipt_commit_v21_308 as retry
from app.api.routes import auron_demo1_telegram_live_terminal_delivery_audit_v21_309 as audit
from app.api.routes import auron_demo1_telegram_provider_registration_v21_292 as provider
from app.main import app


def setup_function() -> None:
    provider.reset_telegram_provider_registration_store()
    original.reset_telegram_live_delivery_state_commit_store()
    retry.reset_telegram_live_retry_receipt_commit_store()
    audit.reset_telegram_live_terminal_delivery_audit_store()


def _original_terminal_chain(state: str = 'delivered') -> str:
    correlation_id = 'correlation-309'
    provider._outbound_store[correlation_id] = {
        'outbound_id': 'outbound-309',
        'correlation_id': correlation_id,
        'delivery_state': state,
    }
    original._live_delivery_commit_store['execution-309'] = {
        'live_delivery_commit_id': 'live-commit-309',
        'execution_id': 'execution-309',
        'correlation_id': correlation_id,
        'activation_id': 'activation-309',
        'provider_id': 'provider-309',
        'runtime_id': 'runtime-309',
        'outbound_id': 'outbound-309',
        'dispatch_id': 'dispatch-309',
        'delivery_state': state,
        'terminal': True,
        'provider_message_id': 'telegram-message-309' if state == 'delivered' else None,
        'provider_error': None if state == 'delivered' else 'chat not found',
    }
    return correlation_id


def _retry_terminal_chain() -> str:
    correlation_id = _original_terminal_chain('retry-required')
    original._live_delivery_commit_store['execution-309']['terminal'] = False
    provider._outbound_store[correlation_id]['delivery_state'] = 'delivered'
    retry._live_retry_commit_store['retry-dispatch-309'] = {
        'live_retry_delivery_commit_id': 'retry-commit-309',
        'live_retry_dispatch_id': 'retry-dispatch-309',
        'live_retry_receipt_id': 'retry-receipt-309',
        'live_retry_id': 'live-retry-309',
        'live_delivery_commit_id': 'live-commit-309',
        'correlation_id': correlation_id,
        'provider_id': 'provider-309',
        'runtime_id': 'runtime-309',
        'outbound_id': 'outbound-309',
        'attempt': 2,
        'max_attempts': 3,
        'accepted': True,
        'provider_message_id': 'telegram-retry-message-309',
        'provider_error': None,
        'http_status': 200,
        'delivery_state': 'delivered',
        'terminal': True,
        'committed_at': '2026-08-02T13:40:00+00:00',
    }
    return correlation_id


def test_original_terminal_delivery_creates_immutable_audit() -> None:
    correlation_id = _original_terminal_chain()
    result = audit.audit_live_terminal_delivery(audit.TelegramLiveTerminalAuditRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-live-terminal-delivery-audited'
    assert result['audit']['final_delivery_state'] == 'delivered'
    assert result['audit']['final_attempt'] == 1
    assert result['audit']['immutable'] is True
    assert result['audit']['integrity_verified'] is True
    assert len(result['audit']['integrity_hash']) == 64
    assert result['external_calls_made'] == 0


def test_retry_terminal_delivery_includes_retry_chain() -> None:
    correlation_id = _retry_terminal_chain()
    result = audit.audit_live_terminal_delivery(audit.TelegramLiveTerminalAuditRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['audit']['final_delivery_state'] == 'delivered'
    assert result['audit']['final_attempt'] == 2
    assert len(result['audit']['retry_attempts']) == 1
    assert result['audit']['retry_attempts'][0]['live_retry_delivery_commit_id'] == 'retry-commit-309'
    assert result['next_layer'] == 'telegram-live-lifecycle-closure'


def test_live_terminal_audit_is_idempotent() -> None:
    correlation_id = _original_terminal_chain()
    payload = audit.TelegramLiveTerminalAuditRequest(correlation_id=correlation_id, actor='brano')
    first = audit.audit_live_terminal_delivery(payload)
    replay = audit.audit_live_terminal_delivery(payload)
    assert replay['idempotent_replay'] is True
    assert replay['audit']['live_terminal_audit_id'] == first['audit']['live_terminal_audit_id']
    assert replay['audit']['integrity_hash'] == first['audit']['integrity_hash']


def test_non_terminal_chain_is_blocked() -> None:
    correlation_id = _original_terminal_chain('retry-required')
    original._live_delivery_commit_store['execution-309']['terminal'] = False
    result = audit.audit_live_terminal_delivery(audit.TelegramLiveTerminalAuditRequest(
        correlation_id=correlation_id, actor='brano'
    ))
    assert result['state'] == 'telegram-live-terminal-delivery-audit-blocked'
    assert 'terminal_source_is_terminal' in result['blockers']
    assert 'terminal_state_supported' in result['blockers']


def test_missing_chain_is_rejected() -> None:
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.309/audit', json={
        'correlation_id': 'missing', 'actor': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.309/command-center')
    assert response.status_code == 200
    assert 'v21.309' in response.text
    assert 'AURON TELEGRAM LIVE TERMINAL DELIVERY AUDIT COMMAND CENTER' in response.text
