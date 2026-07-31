from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_downstream_state_commit_v21_275 import (
    DownstreamStateCommitRequest,
    commit_downstream_state,
    reset_downstream_state_store,
)
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_downstream_state_store()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'commit verified downstream state',
                'session_id': 'v275',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='downstream state commit test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _verification_receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'verified_by': 'brano',
        'session_id': 'v275',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'dispatch_verified': True,
        'adapter_result_verified': True,
        'adapter_reference': 'ref-275',
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v275',
        workspace_id='demo',
        operator_id='brano',
        verification_receipt=_verification_receipt(record),
        downstream_state={'status': 'completed', 'reference': 'ref-275'},
        expected_version=0,
        commit=True,
    )
    data.update(overrides)
    return DownstreamStateCommitRequest(**data)


def test_verified_state_can_be_committed_once() -> None:
    record = _consumed()
    result = commit_downstream_state(_payload(record))
    assert result['state'] == 'downstream-state-committed'
    assert result['state_receipt']['downstream_state_committed'] is True
    assert result['state_receipt']['version'] == 1
    assert result['external_calls_made'] == 0
    assert result['mutations_made'] == 1
    assert result['next_gate'] == 'post-commit-audit'


def test_identical_replay_is_idempotent() -> None:
    record = _consumed()
    commit_downstream_state(_payload(record))
    result = commit_downstream_state(_payload(record))
    assert result['state'] == 'downstream-state-already-committed'
    assert result['idempotent_replay'] is True
    assert result['mutations_made'] == 0
    assert result['version'] == 1


def test_conflicting_state_requires_current_version() -> None:
    record = _consumed()
    commit_downstream_state(_payload(record))
    result = commit_downstream_state(
        _payload(record, downstream_state={'status': 'changed'}, expected_version=0)
    )
    assert result['state'] == 'downstream-state-version-conflict'
    assert result['current_version'] == 1
    assert result['mutations_made'] == 0
    assert result['next_gate'] == 'downstream-state-reconcile'


def test_invalid_verification_receipt_fails_closed() -> None:
    record = _consumed()
    result = commit_downstream_state(
        _payload(record, verification_receipt=_verification_receipt(record, adapter_result_verified=False))
    )
    assert result['state'] == 'downstream-state-commit-blocked'
    assert 'adapter_result_verified' in result['blockers']
    assert result['mutations_made'] == 0


def test_commit_can_be_declined_without_mutation() -> None:
    record = _consumed()
    result = commit_downstream_state(_payload(record, commit=False))
    assert result['state'] == 'downstream-state-commit-declined'
    assert result['mutations_made'] == 0


def test_routes_are_registered() -> None:
    record = _consumed()
    client = TestClient(app)
    response = client.get(f'/auron/demo1/v21.275/state/{record.id}')
    assert response.status_code == 200
    command = client.get('/auron/demo1/v21.275/command-center')
    assert command.status_code == 200
    assert 'v21.275' in command.text
    assert 'AURON DOWNSTREAM STATE COMMIT COMMAND CENTER' in command.text
