from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_downstream_state_commit_v21_275 import (
    DownstreamStateCommitRequest,
    commit_downstream_state,
    reset_downstream_state_store,
)
from app.api.routes.auron_demo1_post_commit_audit_v21_276 import (
    PostCommitAuditRequest,
    audit_post_commit,
    reset_post_commit_audit_store,
)
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_downstream_state_store()
    reset_post_commit_audit_store()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'execute governed action',
                'session_id': 'v276',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='post commit audit test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _verification_receipt(record):
    return {
        'approval_id': str(record.id),
        'verified_by': 'brano',
        'session_id': 'v276',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'dispatch_verified': True,
        'adapter_result_verified': True,
        'adapter_reference': 'ref-276',
    }


def _commit(record):
    return commit_downstream_state(
        DownstreamStateCommitRequest(
            approval_id=record.id,
            actor='brano',
            session_id='v276',
            workspace_id='demo',
            operator_id='brano',
            verification_receipt=_verification_receipt(record),
            downstream_state={'status': 'applied', 'reference': 'ref-276'},
            expected_version=0,
            commit=True,
        )
    )


def _audit_payload(record, state_receipt):
    return PostCommitAuditRequest(
        approval_id=record.id,
        actor='brano',
        session_id='v276',
        workspace_id='demo',
        operator_id='brano',
        state_receipt=state_receipt,
    )


def test_post_commit_audit_closes_execution_chain() -> None:
    record = _consumed()
    committed = _commit(record)
    result = audit_post_commit(_audit_payload(record, committed['state_receipt']))

    assert result['state'] == 'post-commit-audit-completed'
    assert result['audit_completed'] is True
    assert result['completion_status'] == 'completed'
    assert result['audit_receipt']['receipt_lineage_verified'] is True
    assert result['audit_receipt']['committed_state_verified'] is True
    assert result['audit_receipt']['execution_chain_complete'] is True
    assert result['external_calls_made'] == 0
    assert result['business_mutations_made'] == 0
    assert result['next_gate'] == 'execution-chain-closed'


def test_tampered_state_receipt_is_blocked() -> None:
    record = _consumed()
    committed = _commit(record)
    receipt = dict(committed['state_receipt'])
    receipt['state_digest'] = '0' * 64

    result = audit_post_commit(_audit_payload(record, receipt))
    assert result['state'] == 'post-commit-audit-blocked'
    assert 'state_digest' in result['blockers']
    assert result['audit_completed'] is False
    assert result['next_gate'] == 'downstream-state-reconcile'


def test_post_commit_audit_is_idempotent() -> None:
    record = _consumed()
    committed = _commit(record)
    payload = _audit_payload(record, committed['state_receipt'])

    first = audit_post_commit(payload)
    second = audit_post_commit(payload)

    assert first['state'] == 'post-commit-audit-completed'
    assert second['state'] == 'post-commit-audit-already-completed'
    assert second['idempotent_replay'] is True
    assert second['audit_receipt'] == first['audit_receipt']


def test_missing_committed_state_is_blocked() -> None:
    record = _consumed()
    fake_receipt = {
        'approval_id': str(record.id),
        'committed_by': 'brano',
        'session_id': 'v276',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'adapter_reference': 'ref-276',
        'state_digest': '1' * 64,
        'version': 1,
        'downstream_state_committed': True,
    }

    result = audit_post_commit(_audit_payload(record, fake_receipt))
    assert result['state'] == 'post-commit-audit-blocked'
    assert 'committed_state_missing' in result['blockers']


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.276/command-center')
    assert response.status_code == 200
    assert 'v21.276' in response.text
    assert 'AURON POST-COMMIT AUDIT COMMAND CENTER' in response.text
