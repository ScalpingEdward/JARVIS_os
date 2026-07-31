from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_approved_resume_gate_v21_262 import ResumeAuthorizationRequest, authorize_resume
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, ApprovalStatus, RiskLevel
from app.approvals.service import approval_service
from app.main import app


def setup_function() -> None:
    approval_service.reset()


def _approved():
    record = approval_service.request(
        ApprovalRequestCreate(
            action='auron.execute.high_risk',
            arguments={
                'command': 'execute governed action',
                'session_id': 'v262',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    return record, token


def test_approved_token_authorizes_resume_without_execution() -> None:
    record, token = _approved()
    result = authorize_resume(
        ResumeAuthorizationRequest(
            approval_id=record.id,
            confirmation_token=token,
            actor='brano',
            session_id='v262',
            workspace_id='demo',
            operator_id='brano',
        )
    )
    assert result['state'] == 'resume-authorized'
    assert result['resume_authorized'] is True
    assert result['execution_performed'] is False
    assert approval_service.get(record.id).status == ApprovalStatus.consumed


def test_scope_mismatch_is_forbidden() -> None:
    record, token = _approved()
    client = TestClient(app)
    response = client.post(
        '/auron/demo1/v21.262/authorize-resume',
        json={
            'approval_id': str(record.id),
            'confirmation_token': token,
            'actor': 'brano',
            'session_id': 'wrong-session',
            'workspace_id': 'demo',
            'operator_id': 'brano',
        },
    )
    assert response.status_code == 403
    assert approval_service.get(record.id).status == ApprovalStatus.approved


def test_token_is_single_use() -> None:
    record, token = _approved()
    payload = ResumeAuthorizationRequest(
        approval_id=record.id,
        confirmation_token=token,
        actor='brano',
        session_id='v262',
        workspace_id='demo',
        operator_id='brano',
    )
    authorize_resume(payload)
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.262/authorize-resume', json=payload.model_dump(mode='json'))
    assert response.status_code == 409


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.262/command-center')
    assert response.status_code == 200
    assert 'v21.262' in response.text
    assert 'AURON APPROVED RESUME GATE COMMAND CENTER' in response.text
