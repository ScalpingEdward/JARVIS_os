from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_adapter_call_commit_v21_272 import AdapterCallCommitRequest, commit_adapter_call
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'execute governed action',
                'session_id': 'v272',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='adapter call commit test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _invocation_receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'prepared_by': 'brano',
        'session_id': 'v272',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'single_use_authorization_consumed': True,
        'runtime_checks_passed': True,
        'invocation_prepared': True,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v272',
        workspace_id='demo',
        operator_id='brano',
        invocation_receipt=_invocation_receipt(record),
        commit=True,
        emergency_stop_clear=True,
        runtime_healthy=True,
        adapter_ready=True,
        credentials_valid=True,
        policy_still_valid=True,
    )
    data.update(overrides)
    return AdapterCallCommitRequest(**data)


def test_commit_produces_receipt_without_external_call() -> None:
    record = _consumed()
    result = commit_adapter_call(_payload(record))
    assert result['state'] == 'adapter-call-committed'
    assert result['commit_receipt']['call_committed'] is True
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['external_calls_made'] == 0
    assert result['mutations_made'] == 0
    assert result['next_gate'] == 'adapter-call-dispatch'


def test_declined_commit_stays_non_executing() -> None:
    record = _consumed()
    result = commit_adapter_call(_payload(record, commit=False))
    assert result['state'] == 'adapter-call-commit-declined'
    assert result['external_calls_made'] == 0
    assert result['mutations_made'] == 0
    assert result['next_gate'] == 'controlled-adapter-boundary'


def test_tampered_invocation_receipt_is_blocked() -> None:
    record = _consumed()
    result = commit_adapter_call(
        _payload(record, invocation_receipt=_invocation_receipt(record, invocation_prepared=False))
    )
    assert result['state'] == 'adapter-call-commit-blocked'
    assert 'invocation_prepared' in result['blockers']
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'controlled-adapter-boundary'


def test_failed_runtime_check_blocks_commit() -> None:
    record = _consumed()
    result = commit_adapter_call(_payload(record, emergency_stop_clear=False))
    assert result['state'] == 'adapter-call-commit-blocked'
    assert 'emergency_stop_clear' in result['blockers']
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'preflight-remediation'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.272/commit', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.272/command-center')
    assert response.status_code == 200
    assert 'v21.272' in response.text
    assert 'AURON ADAPTER CALL COMMIT COMMAND CENTER' in response.text
