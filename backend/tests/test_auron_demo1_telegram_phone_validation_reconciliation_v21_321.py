from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import _dispatch_store
from app.api.routes.auron_demo1_telegram_inbound_lifecycle_closure_audit_v21_319 import _closure_audit_store
from app.api.routes.auron_demo1_telegram_inbound_webhook_receiver_v21_314 import _webhook_receipt_store
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _message_store
from app.api.routes.auron_demo1_telegram_operational_readiness_observability_v21_320 import _validation_run_store
from app.api.routes.auron_demo1_telegram_runtime_result_correlation_v21_318 import _result_commit_store
from app.api.routes.auron_demo1_telegram_phone_validation_reconciliation_v21_321 import (
    reset_telegram_phone_validation_reconciliation_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_phone_validation_reconciliation_store()
    _validation_run_store.clear()
    _webhook_receipt_store.clear()
    _message_store.clear()
    _dispatch_store.clear()
    _result_commit_store.clear()
    _closure_audit_store.clear()


def _seed_complete_flow() -> None:
    _validation_run_store['1001'] = {
        'validation_run_id': 'run-1',
        'readiness_id': 'ready-1',
        'telegram_chat_id': '1001',
        'telegram_user_id': '2001',
        'operator_id': 'operator-1',
        'workspace_id': 'workspace-1',
        'test_message': 'AURON phone validation',
        'run_state': 'prepared-awaiting-phone-message',
    }
    _webhook_receipt_store['9001'] = {
        'webhook_receipt_id': 'receipt-1',
        'secret_verified': True,
    }
    _message_store['9001'] = {
        'text': 'AURON phone validation',
        'telegram_chat_id': '1001',
        'operator_id': 'operator-1',
        'workspace_id': 'workspace-1',
    }
    _dispatch_store['9001'] = {'dispatch_id': 'dispatch-1'}
    _result_commit_store['9001'] = {
        'result_commit_id': 'commit-1',
        'delivery_state': 'delivered',
        'provider_message_id': '777',
    }
    _closure_audit_store['9001'] = {
        'closure_id': 'closure-1',
        'terminal_state': 'delivered',
        'immutable': True,
    }


def test_phone_validation_passes_with_complete_evidence() -> None:
    _seed_complete_flow()
    response = client.post('/auron/demo1/v21.321/reconcile', json={
        'actor': 'tester',
        'validation_run_id': 'run-1',
        'update_id': '9001',
        'phone_reply_observed': True,
        'observed_provider_message_id': '777',
    })
    assert response.status_code == 200
    data = response.json()
    assert data['state'] == 'telegram-phone-validation-passed'
    assert data['reconciliation']['validation_passed'] is True
    assert data['reconciliation']['immutable'] is True
    assert len(data['reconciliation']['integrity_hash']) == 64
    assert _validation_run_store['1001']['run_state'] == 'passed'


def test_phone_validation_fails_when_phone_reply_is_not_observed() -> None:
    _seed_complete_flow()
    response = client.post('/auron/demo1/v21.321/reconcile', json={
        'actor': 'tester',
        'validation_run_id': 'run-1',
        'update_id': '9001',
        'phone_reply_observed': False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data['state'] == 'telegram-phone-validation-failed'
    assert 'phone_reply_observed' in data['reconciliation']['blockers']


def test_reconciliation_is_idempotent() -> None:
    _seed_complete_flow()
    payload = {
        'actor': 'tester',
        'validation_run_id': 'run-1',
        'update_id': '9001',
        'phone_reply_observed': True,
        'observed_provider_message_id': '777',
    }
    first = client.post('/auron/demo1/v21.321/reconcile', json=payload)
    second = client.post('/auron/demo1/v21.321/reconcile', json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['idempotent_replay'] is True
    assert second.json()['reconciliation']['reconciliation_id'] == first.json()['reconciliation']['reconciliation_id']


def test_mismatched_provider_message_is_blocked_as_failed_evidence() -> None:
    _seed_complete_flow()
    response = client.post('/auron/demo1/v21.321/reconcile', json={
        'actor': 'tester',
        'validation_run_id': 'run-1',
        'update_id': '9001',
        'phone_reply_observed': True,
        'observed_provider_message_id': 'wrong',
    })
    assert response.status_code == 200
    assert 'observed_provider_message_matches' in response.json()['reconciliation']['blockers']


def test_command_center_is_registered() -> None:
    response = client.get('/auron/demo1/v21.321/command-center')
    assert response.status_code == 200
    assert 'PHONE VALIDATION RECONCILIATION' in response.text
