from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_adapter_result_verification_v21_274 import (
    AdapterResultVerificationRequest,
    verify_adapter_result,
)
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
                'session_id': 'v274',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='adapter result verification test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _dispatch_receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'dispatched_by': 'brano',
        'session_id': 'v274',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'call_committed': True,
        'adapter_invoked': True,
        'external_calls_made': 1,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v274',
        workspace_id='demo',
        operator_id='brano',
        dispatch_receipt=_dispatch_receipt(record),
        adapter_result={'ok': True, 'reference': 'ref-274'},
        require_ok=True,
        expected_reference='ref-274',
    )
    data.update(overrides)
    return AdapterResultVerificationRequest(**data)


def test_verified_result_advances_without_new_external_call() -> None:
    record = _consumed()
    result = verify_adapter_result(_payload(record))
    assert result['state'] == 'adapter-result-verified'
    assert result['verified'] is True
    assert result['verification_receipt']['adapter_result_verified'] is True
    assert result['external_calls_made'] == 0
    assert result['mutations_made'] == 0
    assert result['next_gate'] == 'downstream-state-commit'


def test_failed_adapter_result_routes_to_recovery() -> None:
    record = _consumed()
    result = verify_adapter_result(_payload(record, adapter_result={'ok': False, 'reference': 'ref-274'}))
    assert result['state'] == 'adapter-result-rejected'
    assert 'result_ok' in result['blockers']
    assert result['external_calls_made'] == 0
    assert result['next_gate'] == 'adapter-failure-recovery'


def test_tampered_dispatch_receipt_is_blocked() -> None:
    record = _consumed()
    result = verify_adapter_result(_payload(record, dispatch_receipt=_dispatch_receipt(record, adapter_invoked=False)))
    assert result['state'] == 'adapter-result-verification-blocked'
    assert 'adapter_invoked' in result['blockers']
    assert result['next_gate'] == 'adapter-call-dispatch'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.274/verify', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.274/command-center')
    assert response.status_code == 200
    assert 'v21.274' in response.text
    assert 'AURON ADAPTER RESULT VERIFICATION COMMAND CENTER' in response.text
