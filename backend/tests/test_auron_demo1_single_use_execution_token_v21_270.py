from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_single_use_execution_token_v21_270 import (
    ExecutionTokenConsumeRequest,
    ExecutionTokenIssueRequest,
    consume_token,
    issue_token,
    reset_token_store,
)
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()
    reset_token_store()


def _consumed():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={
                'command': 'execute governed action',
                'session_id': 'v270',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='single-use authorization test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _arm_receipt(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'armed_by': 'brano',
        'session_id': 'v270',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'predicted_risk': 'high',
        'operator_confirmed': True,
        'safety_checks_passed': True,
        'armed': True,
    }
    data.update(overrides)
    return data


def _issue_payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v270',
        workspace_id='demo',
        operator_id='brano',
        arm_receipt=_arm_receipt(record),
    )
    data.update(overrides)
    return ExecutionTokenIssueRequest(**data)


def test_issue_token_is_non_executing_and_single_use() -> None:
    record = _consumed()
    issued = issue_token(_issue_payload(record))
    assert issued['state'] == 'single-use-token-issued'
    assert issued['single_use'] is True
    assert issued['execution_performed'] is False
    assert issued['adapter_invoked'] is False

    consumed = consume_token(
        ExecutionTokenConsumeRequest(
            approval_id=record.id,
            session_id='v270',
            workspace_id='demo',
            operator_id='brano',
            token=issued['execution_token'],
        )
    )
    assert consumed['state'] == 'execution-token-consumed'
    assert consumed['authorization_receipt']['single_use_enforced'] is True
    assert consumed['execution_performed'] is False
    assert consumed['adapter_invoked'] is False
    assert consumed['next_gate'] == 'live-adapter-invocation'


def test_second_consume_is_rejected() -> None:
    record = _consumed()
    issued = issue_token(_issue_payload(record))
    payload = ExecutionTokenConsumeRequest(
        approval_id=record.id,
        session_id='v270',
        workspace_id='demo',
        operator_id='brano',
        token=issued['execution_token'],
    )
    consume_token(payload)
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.270/consume', json=payload.model_dump(mode='json'))
    assert response.status_code == 409
    assert 'already used' in response.json()['detail']


def test_invalid_arm_receipt_blocks_issuance() -> None:
    record = _consumed()
    result = issue_token(_issue_payload(record, arm_receipt=_arm_receipt(record, armed=False)))
    assert result['state'] == 'token-issuance-blocked'
    assert 'armed' in result['blockers']
    assert result['next_gate'] == 'live-execution-arm-gate'


def test_wrong_token_is_rejected() -> None:
    record = _consumed()
    issue_token(_issue_payload(record))
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.270/consume',
        json={
            'approval_id': str(record.id),
            'session_id': 'v270',
            'workspace_id': 'demo',
            'operator_id': 'brano',
            'token': 'x' * 32,
        },
    )
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.270/command-center')
    assert response.status_code == 200
    assert 'v21.270' in response.text
    assert 'AURON SINGLE-USE EXECUTION TOKEN COMMAND CENTER' in response.text
