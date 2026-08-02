from fastapi.testclient import TestClient

from app.api.routes import auron_demo1_alert_delivery_commit_audit_v21_288 as audit
from app.api.routes import auron_demo1_alert_delivery_state_commit_v21_287 as commit
from app.main import app


def setup_function() -> None:
    commit.reset_delivery_state_commit_store()
    audit.reset_delivery_commit_audit_store()


def _commit() -> str:
    commit_id = 'commit-288'
    commit._commit_store[commit_id] = {
        'commit_id': commit_id,
        'delivery_id': 'delivery-288',
        'retry_result_id': 'result-288',
        'retry_dispatch_id': 'retry-dispatch-288',
        'dispatch_id': 'dispatch-288',
        'attempt': 2,
        'provider_status': 'delivered',
        'provider_receipt_id': 'provider-288',
        'previous_delivery_state': 'prepared-not-dispatched',
        'committed_delivery_state': 'verified-delivered',
        'committed_by': 'brano',
        'committed_at': '2026-08-02T10:00:00+00:00',
        'note': None,
    }
    return commit_id


def test_commit_audit_creates_immutable_integrity_receipt() -> None:
    result = audit.audit_delivery_commit(
        _commit(),
        audit.DeliveryCommitAuditRequest(actor='brano'),
    )
    receipt = result['receipt']
    assert result['state'] == 'alert-delivery-commit-audited'
    assert receipt['immutable'] is True
    assert receipt['integrity_verified'] is True
    assert receipt['hash_algorithm'] == 'sha256'
    assert len(receipt['integrity_hash']) == 64
    assert receipt['audit_version'] == 'v21.288'
    assert result['external_calls_made'] == 0
    assert result['terminal_execution_state_modified'] is False


def test_same_commit_audit_is_idempotent() -> None:
    commit_id = _commit()
    payload = audit.DeliveryCommitAuditRequest(actor='brano')
    first = audit.audit_delivery_commit(commit_id, payload)
    replay = audit.audit_delivery_commit(commit_id, payload)
    assert replay['state'] == 'alert-delivery-commit-already-audited'
    assert replay['idempotent_replay'] is True
    assert replay['receipt']['audit_id'] == first['receipt']['audit_id']
    assert replay['receipt']['integrity_hash'] == first['receipt']['integrity_hash']


def test_integrity_hash_is_deterministic_for_same_commit_payload() -> None:
    commit_id = _commit()
    source = commit._commit_store[commit_id]
    first = audit._canonical_hash(audit._integrity_payload(source))
    second = audit._canonical_hash(audit._integrity_payload(dict(source)))
    assert first == second


def test_unknown_commit_cannot_be_audited() -> None:
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.288/audit/missing',
        json={'actor': 'brano'},
    )
    assert response.status_code == 404
    assert 'commit not found' in response.json()['detail'].lower()


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.288/command-center')
    assert response.status_code == 200
    assert 'v21.288' in response.text
    assert 'AURON ALERT DELIVERY COMMIT AUDIT COMMAND CENTER' in response.text
