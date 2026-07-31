from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_execution_dispatch_gate_v21_263 import DispatchRequest, prepare_dispatch
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()


def _consumed(action: str = 'auron.execute.high_risk'):
    record = approval_service.request(
        ApprovalRequestCreate(
            action=action,
            arguments={
                'command': 'execute governed action',
                'session_id': 'v263',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='test dispatch',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def test_consumed_approval_prepares_dispatch_without_execution() -> None:
    record = _consumed()
    result = prepare_dispatch(
        DispatchRequest(
            approval_id=record.id,
            actor='brano',
            session_id='v263',
            workspace_id='demo',
            operator_id='brano',
        )
    )
    assert result['state'] == 'dispatch-prepared'
    assert result['dispatch_ready'] is True
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'execution-adapter-selection'


def test_unconsumed_approval_cannot_dispatch() -> None:
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.execute.high_risk',
            arguments={'command': 'x', 'session_id': 'v263', 'workspace_id': 'demo'},
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='test',
        )
    )
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.263/prepare-dispatch', json={
        'approval_id': str(record.id), 'actor': 'brano', 'session_id': 'v263',
        'workspace_id': 'demo', 'operator_id': 'brano'
    })
    assert response.status_code == 409


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.263/prepare-dispatch', json={
        'approval_id': str(record.id), 'actor': 'brano', 'session_id': 'wrong',
        'workspace_id': 'demo', 'operator_id': 'brano'
    })
    assert response.status_code == 403


def test_financial_action_is_classified_protected() -> None:
    record = _consumed('auron.mt5.trade.execute')
    result = prepare_dispatch(DispatchRequest(
        approval_id=record.id, actor='brano', session_id='v263', workspace_id='demo', operator_id='brano'
    ))
    assert result['dispatch_class'] == 'financial-protected'
    assert result['execution_performed'] is False


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.263/command-center')
    assert response.status_code == 200
    assert 'v21.263' in response.text
    assert 'AURON EXECUTION DISPATCH GATE COMMAND CENTER' in response.text
