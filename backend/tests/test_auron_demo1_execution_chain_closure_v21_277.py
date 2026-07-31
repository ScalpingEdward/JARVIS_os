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
from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import (
    ExecutionChainClosureRequest,
    close_execution_chain,
    reset_execution_chain_closure_store,
)
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_downstream_state_store()
    reset_post_commit_audit_store()
    reset_execution_chain_closure_store()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'finalize governed execution chain',
                'session_id': 'v277',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='execution chain closure test',
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
        'session_id': 'v277',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'dispatch_verified': True,
        'adapter_result_verified': True,
        'adapter_reference': 'ref-277',
    }


def _audit(record):
    committed = commit_downstream_state(
        DownstreamStateCommitRequest(
            approval_id=record.id,
            actor='brano',
            session_id='v277',
            workspace_id='demo',
            operator_id='brano',
            verification_receipt=_verification_receipt(record),
            downstream_state={'status': 'applied', 'reference': 'ref-277'},
            expected_version=0,
            commit=True,
        )
    )
    return audit_post_commit(
        PostCommitAuditRequest(
            approval_id=record.id,
            actor='brano',
            session_id='v277',
            workspace_id='demo',
            operator_id='brano',
            state_receipt=committed['state_receipt'],
        )
    )


def _payload(record, audit_receipt):
    return ExecutionChainClosureRequest(
        approval_id=record.id,
        actor='brano',
        session_id='v277',
        workspace_id='demo',
        operator_id='brano',
        audit_receipt=audit_receipt,
    )


def test_execution_chain_closure_creates_immutable_snapshot() -> None:
    record = _consumed()
    audited = _audit(record)
    result = close_execution_chain(_payload(record, audited['audit_receipt']))

    assert result['state'] == 'execution-chain-closed'
    assert result['closed'] is True
    assert result['completion_status'] == 'finalized'
    assert result['immutable_snapshot']['execution_chain_complete'] is True
    assert result['immutable_snapshot']['lifecycle_finalized'] is True
    assert result['closure_receipt']['immutable_snapshot_created'] is True
    assert len(result['snapshot_digest']) == 64
    assert result['external_calls_made'] == 0
    assert result['business_mutations_made'] == 0
    assert result['next_gate'] == 'execution-lifecycle-finalized'


def test_tampered_audit_receipt_is_blocked() -> None:
    record = _consumed()
    audited = _audit(record)
    receipt = dict(audited['audit_receipt'])
    receipt['state_digest'] = '0' * 64

    result = close_execution_chain(_payload(record, receipt))
    assert result['state'] == 'execution-chain-closure-blocked'
    assert 'audit_receipt_mismatch' in result['blockers']
    assert 'state_digest' in result['blockers']
    assert result['closed'] is False
    assert result['next_gate'] == 'post-commit-audit'


def test_closure_is_idempotent() -> None:
    record = _consumed()
    audited = _audit(record)
    payload = _payload(record, audited['audit_receipt'])

    first = close_execution_chain(payload)
    second = close_execution_chain(payload)

    assert first['state'] == 'execution-chain-closed'
    assert second['state'] == 'execution-chain-already-closed'
    assert second['idempotent_replay'] is True
    assert second['snapshot_digest'] == first['snapshot_digest']
    assert second['immutable_snapshot'] == first['immutable_snapshot']


def test_missing_audit_record_is_blocked() -> None:
    record = _consumed()
    fake_receipt = {
        'approval_id': str(record.id),
        'audited_by': 'brano',
        'session_id': 'v277',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'adapter_reference': 'ref-277',
        'state_digest': '1' * 64,
        'state_version': 1,
        'receipt_lineage_verified': True,
        'committed_state_verified': True,
        'execution_chain_complete': True,
    }

    result = close_execution_chain(_payload(record, fake_receipt))
    assert result['state'] == 'execution-chain-closure-blocked'
    assert 'audit_record_missing' in result['blockers']
    assert 'committed_state_missing' in result['blockers']


def test_routes_are_registered() -> None:
    record = _consumed()
    client = TestClient(app)
    response = client.get(f'/auron/demo1/v21.277/closure-status/{record.id}')
    assert response.status_code == 200
    command = client.get('/auron/demo1/v21.277/command-center')
    assert command.status_code == 200
    assert 'v21.277' in command.text
    assert 'AURON EXECUTION CHAIN CLOSURE COMMAND CENTER' in command.text
