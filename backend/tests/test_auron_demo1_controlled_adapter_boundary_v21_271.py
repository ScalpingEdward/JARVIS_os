from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_controlled_adapter_boundary_v21_271 import ControlledAdapterBoundaryRequest, prepare_invocation
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={'session_id': 'v271', 'workspace_id': 'demo', 'operator_id': 'brano'},
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='controlled adapter boundary test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'session_id': 'v271',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'token_consumed': True,
        'single_use_enforced': True,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v271',
        workspace_id='demo',
        operator_id='brano',
        authorization_receipt=_receipt(record),
    )
    data.update(overrides)
    return ControlledAdapterBoundaryRequest(**data)


def test_valid_authorization_prepares_invocation_without_external_call() -> None:
    result = prepare_invocation(_payload(_consumed()))
    assert result['state'] == 'adapter-invocation-prepared'
    assert result['invocation_receipt']['invocation_prepared'] is True
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['external_calls_made'] == 0
    assert result['mutations_made'] == 0
    assert result['next_gate'] == 'adapter-call-commit'


def test_unconsumed_authorization_receipt_is_blocked() -> None:
    record = _consumed()
    result = prepare_invocation(_payload(record, authorization_receipt=_receipt(record, token_consumed=False)))
    assert result['state'] == 'adapter-boundary-blocked'
    assert 'token_consumed' in result['blockers']


def test_emergency_stop_blocks_boundary() -> None:
    result = prepare_invocation(_payload(_consumed(), emergency_stop_clear=False))
    assert result['state'] == 'adapter-boundary-blocked'
    assert 'emergency_stop_clear' in result['blockers']
    assert result['adapter_invoked'] is False


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.271/prepare-invocation', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.271/command-center')
    assert response.status_code == 200
    assert 'v21.271' in response.text
    assert 'AURON CONTROLLED ADAPTER BOUNDARY COMMAND CENTER' in response.text
