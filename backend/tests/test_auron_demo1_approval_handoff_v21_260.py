from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_approval_handoff_v21_260 import dialogue, pending
from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.approvals.models import ApprovalStatus
from app.approvals.service import approval_service
from app.main import app


def _req(command: str, session_id: str = 'v260-test') -> DialogueRequest:
    return DialogueRequest(session_id=session_id, workspace_id='demo', operator_id='brano', command=command)


def setup_function() -> None:
    approval_service.reset()


def test_high_risk_command_creates_pending_approval_without_execution() -> None:
    result = dialogue(_req('execute MT5 trade'))
    assert result['state'] == 'approval-required'
    assert result['mode'] == 'approval-handoff-created'
    assert result['execution_performed'] is False
    assert result['approval']['status'] == ApprovalStatus.pending.value
    assert len(approval_service.list(status=ApprovalStatus.pending)) == 1


def test_duplicate_pending_approval_is_reused() -> None:
    first = dialogue(_req('execute MT5 trade'))
    second = dialogue(_req('execute MT5 trade'))
    assert first['approval']['approval_id'] == second['approval']['approval_id']
    assert len(approval_service.list(status=ApprovalStatus.pending)) == 1


def test_low_risk_or_observe_command_does_not_create_approval() -> None:
    result = dialogue(_req('system health'))
    assert result['approval_handoff'] == {'required': False, 'created': False}
    assert approval_service.list(status=ApprovalStatus.pending) == []


def test_pending_status_is_scoped_to_session_and_operator() -> None:
    dialogue(_req('execute MT5 trade', session_id='one'))
    dialogue(_req('execute MT5 trade', session_id='two'))
    result = pending(session_id='one', workspace_id='demo', operator_id='brano')
    assert result['count'] == 1
    assert result['items'][0]['command'] == 'execute MT5 trade'


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.260/command-center')
    assert response.status_code == 200
    assert 'v21.260' in response.text
    assert 'AURON APPROVAL HANDOFF COMMAND CENTER' in response.text
