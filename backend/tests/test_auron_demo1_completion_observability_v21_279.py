from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_completion_observability_v21_279 import (
    completion_health,
    completion_metrics,
    integrity_failures,
)
from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import (
    _closure_store,
    reset_execution_chain_closure_store,
)
from app.main import app


def setup_function() -> None:
    reset_execution_chain_closure_store()


def _record(approval_id: str, workspace: str = 'demo', operator: str = 'brano') -> None:
    snapshot = {
        'approval_id': approval_id,
        'session_id': 'v279',
        'workspace_id': workspace,
        'operator_id': operator,
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'adapter_reference': f'ref-{approval_id}',
        'state_digest': 'a' * 64,
        'state_version': 1,
        'audit_receipt_digest': 'b' * 64,
        'receipt_lineage_verified': True,
        'committed_state_verified': True,
        'execution_chain_complete': True,
        'lifecycle_finalized': True,
    }
    from app.api.routes.auron_demo1_execution_chain_closure_v21_277 import _canonical_digest

    digest = _canonical_digest(snapshot)
    _closure_store[approval_id] = {
        'snapshot_digest': digest,
        'immutable_snapshot': snapshot,
        'closure_receipt': {
            'approval_id': approval_id,
            'snapshot_digest': digest,
            'immutable_snapshot_created': True,
            'execution_chain_closed': True,
            'lifecycle_finalized': True,
        },
    }


def test_health_is_healthy_for_verified_snapshots() -> None:
    _record('1')
    _record('2')
    result = completion_health()
    assert result['status'] == 'healthy'
    assert result['health_percent'] == 100.0
    assert result['integrity_verified'] == 2
    assert result['integrity_failed'] == 0
    assert result['read_only'] is True


def test_health_degrades_when_snapshot_is_tampered() -> None:
    _record('1')
    _record('2')
    _closure_store['2']['immutable_snapshot']['state_version'] = 9
    result = completion_health()
    assert result['status'] == 'degraded'
    assert result['integrity_verified'] == 1
    assert result['integrity_failed'] == 1
    assert result['health_percent'] == 50.0


def test_metrics_group_by_dimensions() -> None:
    _record('1', workspace='alpha', operator='brano')
    _record('2', workspace='beta', operator='ons')
    result = completion_metrics()
    assert result['health']['finalized_executions'] == 2
    assert {row['workspace_id'] for row in result['by_workspace']} == {'alpha', 'beta'}
    assert {row['operator_id'] for row in result['by_operator']} == {'brano', 'ons'}
    assert result['external_calls_made'] == 0
    assert result['business_mutations_made'] == 0


def test_integrity_failures_expose_reason_without_mutation() -> None:
    _record('1')
    _closure_store['1']['closure_receipt']['snapshot_digest'] = '0' * 64
    result = integrity_failures(limit=100)
    assert result['total_failures'] == 1
    assert 'closure_receipt_mismatch' in result['items'][0]['reasons']
    assert result['read_only'] is True


def test_routes_are_registered() -> None:
    client = TestClient(app)
    health = client.get('/auron/demo1/v21.279/health')
    metrics = client.get('/auron/demo1/v21.279/metrics')
    dashboard = client.get('/auron/demo1/v21.279/dashboard')
    command = client.get('/auron/demo1/v21.279/command-center')
    assert health.status_code == 200
    assert metrics.status_code == 200
    assert dashboard.status_code == 200
    assert command.status_code == 200
    assert 'v21.279' in command.text
    assert 'AURON COMPLETION OBSERVABILITY COMMAND CENTER' in command.text
