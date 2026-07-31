from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_execution_adapter_selection_v21_264 import AdapterSelectionRequest, select_adapter
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()


def _consumed(action: str):
    record = approval_service.request(
        ApprovalRequestCreate(
            action=action,
            arguments={
                'command': 'execute selected action',
                'session_id': 'v264',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='adapter selection test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _select(record):
    return select_adapter(AdapterSelectionRequest(
        approval_id=record.id,
        actor='brano',
        session_id='v264',
        workspace_id='demo',
        operator_id='brano',
    ))


def test_mt5_action_selects_protected_financial_adapter_without_invocation() -> None:
    result = _select(_consumed('auron.mt5.trade.execute'))
    assert result['adapter'] == 'mt5-protected-adapter'
    assert result['execution_domain'] == 'financial'
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'adapter-preflight'


def test_github_action_selects_remote_adapter() -> None:
    result = _select(_consumed('auron.github.repository.update'))
    assert result['adapter'] == 'github-remote-adapter'
    assert result['execution_domain'] == 'code-remote'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed('auron.github.repository.update')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.264/select-adapter', json={
        'approval_id': str(record.id), 'actor': 'brano', 'session_id': 'wrong',
        'workspace_id': 'demo', 'operator_id': 'brano'
    })
    assert response.status_code == 403


def test_unconsumed_approval_cannot_select_adapter() -> None:
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.github.repository.update',
            arguments={'command': 'x', 'session_id': 'v264', 'workspace_id': 'demo'},
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='test',
        )
    )
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.264/select-adapter', json={
        'approval_id': str(record.id), 'actor': 'brano', 'session_id': 'v264',
        'workspace_id': 'demo', 'operator_id': 'brano'
    })
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.264/command-center')
    assert response.status_code == 200
    assert 'v21.264' in response.text
    assert 'AURON EXECUTION ADAPTER SELECTION COMMAND CENTER' in response.text
