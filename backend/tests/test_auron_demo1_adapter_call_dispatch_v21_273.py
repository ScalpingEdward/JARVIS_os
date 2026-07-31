from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_adapter_call_dispatch_v21_273 import (
    AdapterCallDispatchRequest,
    dispatch_adapter_call,
    register_dispatch_adapter,
    reset_dispatch_adapters,
)
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_dispatch_adapters()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'execute governed action',
                'session_id': 'v273',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='adapter dispatch test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _commit_receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'committed_by': 'brano',
        'session_id': 'v273',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'single_use_authorization_consumed': True,
        'runtime_checks_passed': True,
        'invocation_prepared': True,
        'call_committed': True,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v273',
        workspace_id='demo',
        operator_id='brano',
        commit_receipt=_commit_receipt(record),
        adapter_payload={'operation': 'test'},
        allow_external_dispatch=False,
        emergency_stop_clear=True,
        runtime_healthy=True,
        adapter_ready=True,
        credentials_valid=True,
        policy_still_valid=True,
    )
    data.update(overrides)
    return AdapterCallDispatchRequest(**data)


def test_dispatch_is_disabled_by_default() -> None:
    record = _consumed()
    result = dispatch_adapter_call(_payload(record))
    assert result['state'] == 'adapter-dispatch-armed'
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'adapter-call-dispatch-enable'


def test_registered_adapter_can_be_invoked_when_explicitly_enabled() -> None:
    record = _consumed()
    seen = []

    def fake_adapter(payload: dict) -> dict:
        seen.append(payload)
        return {'ok': True, 'reference': 'fake-1'}

    register_dispatch_adapter('github-remote-adapter', fake_adapter)
    result = dispatch_adapter_call(_payload(record, allow_external_dispatch=True))
    assert result['state'] == 'adapter-dispatched'
    assert result['adapter_invoked'] is True
    assert result['execution_performed'] is True
    assert result['external_calls_made'] == 1
    assert result['adapter_result']['ok'] is True
    assert len(seen) == 1
    assert result['next_gate'] == 'adapter-result-verification'


def test_unregistered_adapter_is_blocked() -> None:
    record = _consumed()
    result = dispatch_adapter_call(_payload(record, allow_external_dispatch=True))
    assert result['state'] == 'adapter-dispatch-blocked'
    assert 'adapter_not_registered' in result['blockers']
    assert result['adapter_invoked'] is False
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'adapter-registration'


def test_tampered_commit_receipt_is_blocked() -> None:
    record = _consumed()
    result = dispatch_adapter_call(
        _payload(record, commit_receipt=_commit_receipt(record, call_committed=False), allow_external_dispatch=True)
    )
    assert result['state'] == 'adapter-dispatch-blocked'
    assert 'call_committed' in result['blockers']
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'adapter-call-commit'


def test_failed_runtime_check_blocks_dispatch() -> None:
    record = _consumed()
    result = dispatch_adapter_call(_payload(record, emergency_stop_clear=False, allow_external_dispatch=True))
    assert result['state'] == 'adapter-dispatch-blocked'
    assert 'emergency_stop_clear' in result['blockers']
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'preflight-remediation'


def test_adapter_failure_is_captured() -> None:
    record = _consumed()

    def broken_adapter(payload: dict) -> dict:
        raise RuntimeError('boom')

    register_dispatch_adapter('github-remote-adapter', broken_adapter)
    result = dispatch_adapter_call(_payload(record, allow_external_dispatch=True))
    assert result['state'] == 'adapter-dispatch-failed'
    assert result['adapter_invoked'] is True
    assert result['execution_performed'] is False
    assert result['external_calls_made'] == 1
    assert result['error_type'] == 'RuntimeError'
    assert result['next_gate'] == 'adapter-failure-recovery'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.273/dispatch', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.273/command-center')
    assert response.status_code == 200
    assert 'v21.273' in response.text
    assert 'AURON ADAPTER CALL DISPATCH COMMAND CENTER' in response.text
