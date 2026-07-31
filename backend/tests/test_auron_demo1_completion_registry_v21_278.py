from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_completion_registry_v21_278 import (
    _canonical_digest,
    completion_detail,
    completion_list,
    completion_summary,
)
from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import (
    _closure_store,
    reset_execution_chain_closure_store,
)
from app.approvals.models import ActorRole, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_execution_chain_closure_store()


def _approval(session_id: str = 'v278', workspace_id: str = 'demo', operator_id: str = 'brano'):
    return approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'observe finalized lifecycle',
                'session_id': session_id,
                'workspace_id': workspace_id,
                'operator_id': operator_id,
            },
            requested_by=operator_id,
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='completion registry test',
        )
    )


def _seed(record, *, workspace_id='demo', operator_id='brano', adapter='github-remote-adapter', execution_domain='code-remote'):
    snapshot = {
        'approval_id': str(record.id),
        'session_id': 'v278',
        'workspace_id': workspace_id,
        'operator_id': operator_id,
        'adapter': adapter,
        'execution_domain': execution_domain,
        'adapter_reference': 'ref-278',
        'state_digest': 'a' * 64,
        'state_version': 1,
        'audit_receipt_digest': 'b' * 64,
        'receipt_lineage_verified': True,
        'committed_state_verified': True,
        'execution_chain_complete': True,
        'lifecycle_finalized': True,
    }
    digest = _canonical_digest(snapshot)
    _closure_store[str(record.id)] = {
        'snapshot_digest': digest,
        'immutable_snapshot': snapshot,
        'closure_receipt': {
            'approval_id': str(record.id),
            'closed_by': operator_id,
            'session_id': 'v278',
            'workspace_id': workspace_id,
            'operator_id': operator_id,
            'snapshot_digest': digest,
            'immutable_snapshot_created': True,
            'execution_chain_closed': True,
            'lifecycle_finalized': True,
        },
    }
    return digest


def test_completion_detail_verifies_snapshot_integrity() -> None:
    record = _approval()
    digest = _seed(record)
    result = completion_detail(record.id)
    assert result['snapshot_digest'] == digest
    assert result['integrity_verified'] is True
    assert result['snapshot_digest_matches'] is True
    assert result['closure_receipt_matches'] is True
    assert result['read_only'] is True
    assert result['external_calls_made'] == 0
    assert result['business_mutations_made'] == 0


def test_tampered_snapshot_is_visible_as_integrity_failure() -> None:
    record = _approval()
    _seed(record)
    _closure_store[str(record.id)]['immutable_snapshot']['state_version'] = 99
    result = completion_detail(record.id)
    assert result['integrity_verified'] is False
    assert result['snapshot_digest_matches'] is False


def test_completion_list_supports_read_only_filters() -> None:
    first = _approval(workspace_id='alpha')
    second = _approval(session_id='v278b', workspace_id='beta', operator_id='ons')
    _seed(first, workspace_id='alpha')
    _seed(second, workspace_id='beta', operator_id='ons', adapter='telegram-adapter', execution_domain='signals')

    result = completion_list(
        workspace_id='beta',
        operator_id=None,
        adapter=None,
        execution_domain=None,
        integrity='all',
        limit=100,
    )
    assert result['count'] == 1
    assert result['items'][0]['workspace_id'] == 'beta'
    assert result['items'][0]['operator_id'] == 'ons'
    assert result['read_only'] is True


def test_integrity_filter_can_surface_failed_snapshots() -> None:
    good = _approval(workspace_id='good')
    bad = _approval(session_id='v278bad', workspace_id='bad', operator_id='ons')
    _seed(good, workspace_id='good')
    _seed(bad, workspace_id='bad', operator_id='ons')
    _closure_store[str(bad.id)]['immutable_snapshot']['state_digest'] = 'c' * 64

    result = completion_list(
        workspace_id=None,
        operator_id=None,
        adapter=None,
        execution_domain=None,
        integrity='failed',
        limit=100,
    )
    assert result['count'] == 1
    assert result['items'][0]['approval_id'] == str(bad.id)
    assert result['items'][0]['integrity_verified'] is False


def test_summary_counts_finalized_and_integrity_states() -> None:
    good = _approval(workspace_id='alpha')
    bad = _approval(session_id='v278c', workspace_id='beta', operator_id='ons')
    _seed(good, workspace_id='alpha')
    _seed(bad, workspace_id='beta', operator_id='ons', adapter='telegram-adapter', execution_domain='signals')
    _closure_store[str(bad.id)]['closure_receipt']['snapshot_digest'] = '0' * 64

    result = completion_summary()
    assert result['finalized_executions'] == 2
    assert result['integrity_verified'] == 1
    assert result['integrity_failed'] == 1
    assert result['workspaces'] == ['alpha', 'beta']
    assert result['read_only'] is True


def test_routes_are_registered() -> None:
    record = _approval()
    _seed(record)
    client = TestClient(app)

    detail = client.get(f'/auron/demo1/v21.278/completion/{record.id}')
    assert detail.status_code == 200
    listing = client.get('/auron/demo1/v21.278/completions')
    assert listing.status_code == 200
    summary = client.get('/auron/demo1/v21.278/summary')
    assert summary.status_code == 200
    command = client.get('/auron/demo1/v21.278/command-center')
    assert command.status_code == 200
    assert 'v21.278' in command.text
    assert 'AURON COMPLETION REGISTRY COMMAND CENTER' in command.text
