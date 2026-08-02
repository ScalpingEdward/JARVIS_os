from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_delivery_commit_audit_v21_288 as audit
from app.api.routes import auron_demo1_alert_delivery_state_commit_v21_287 as commit
from app.api.routes import auron_demo1_alert_lifecycle_closure_v21_289 as closure
from app.api.routes import auron_demo1_completion_alert_delivery_boundary_v21_281 as delivery
from app.main import app


def setup_function() -> None:
    delivery.reset_alert_delivery_store()
    commit.reset_delivery_state_commit_store()
    audit.reset_delivery_commit_audit_store()
    closure.reset_alert_lifecycle_closure_store()


def _complete_chain() -> str:
    delivery_id = 'delivery-289'
    commit_id = 'commit-289'
    delivery._delivery_store[delivery_id] = {
        'delivery_id': delivery_id,
        'delivery_state': 'verified-delivered',
        'delivery_state_commit_id': commit_id,
        'terminal': True,
        'acknowledged': False,
    }
    commit._commit_store[commit_id] = {
        'commit_id': commit_id,
        'delivery_id': delivery_id,
        'retry_result_id': 'result-289',
        'retry_dispatch_id': 'retry-dispatch-289',
        'dispatch_id': 'dispatch-289',
        'attempt': 2,
        'provider_status': 'delivered',
        'provider_receipt_id': 'provider-289',
        'committed_delivery_state': 'verified-delivered',
        'committed_by': 'brano',
        'committed_at': '2026-08-02T10:00:00+00:00',
    }
    audit._audit_store['audit-289'] = {
        'audit_id': 'audit-289',
        'commit_id': commit_id,
        'delivery_id': delivery_id,
        'dispatch_id': 'dispatch-289',
        'retry_dispatch_id': 'retry-dispatch-289',
        'retry_result_id': 'result-289',
        'integrity_hash': 'a' * 64,
        'integrity_verified': True,
        'immutable': True,
    }
    return commit_id


def test_complete_chain_closes_and_archives_lifecycle() -> None:
    commit_id = _complete_chain()
    result = closure.close_alert_lifecycle(
        commit_id,
        closure.AlertLifecycleClosureRequest(actor='brano', archive=True),
    )
    assert result['state'] == 'alert-lifecycle-closed'
    assert result['closure']['chain_complete'] is True
    assert result['closure']['lifecycle_closed'] is True
    assert result['closure']['archived'] is True
    assert delivery._delivery_store['delivery-289']['lifecycle_closed'] is True
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_missing_audit_blocks_closure() -> None:
    commit_id = _complete_chain()
    audit.reset_delivery_commit_audit_store()
    client = TestClient(app)
    response = client.post(
        f'/auron/demo1/v21.289/close/{commit_id}',
        json={'actor': 'brano', 'archive': True},
    )
    assert response.status_code == 409
    assert 'audit receipt required' in response.json()['detail'].lower()


def test_integrity_mismatch_returns_blockers() -> None:
    commit_id = _complete_chain()
    delivery._delivery_store['delivery-289']['delivery_state'] = 'permanent-failure'
    result = closure.close_alert_lifecycle(
        commit_id,
        closure.AlertLifecycleClosureRequest(actor='brano'),
    )
    assert result['state'] == 'alert-lifecycle-closure-blocked'
    assert 'delivery_state_matches_commit' in result['blockers']


def test_lifecycle_closure_is_idempotent() -> None:
    commit_id = _complete_chain()
    payload = closure.AlertLifecycleClosureRequest(actor='brano')
    first = closure.close_alert_lifecycle(commit_id, payload)
    replay = closure.close_alert_lifecycle(commit_id, payload)
    assert replay['state'] == 'alert-lifecycle-already-closed'
    assert replay['idempotent_replay'] is True
    assert replay['closure']['closure_id'] == first['closure']['closure_id']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.289/command-center')
    assert response.status_code == 200
    assert 'v21.289' in response.text
    assert 'AURON ALERT LIFECYCLE CLOSURE COMMAND CENTER' in response.text
