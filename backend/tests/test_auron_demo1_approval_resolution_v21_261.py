from app.api.routes.auron_demo1_approval_resolution_v21_261 import resolution_status
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalRequestCreate, RiskLevel
from app.approvals.service import approval_service


def setup_function() -> None:
    approval_service.reset()


def _request():
    return approval_service.request(
        ApprovalRequestCreate(
            action='auron.execute.high_risk',
            arguments={
                'command': 'execute protected action',
                'session_id': 's1',
                'workspace_id': 'w1',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='approval required',
        )
    )


def test_resolution_status_tracks_pending_approval() -> None:
    _request()
    result = resolution_status('s1', 'w1', 'brano')
    assert result['count'] == 1
    assert result['pending'] == 1
    assert result['approved'] == 0
    assert result['resume_ready'] is False


def test_resolution_status_marks_approved_as_resume_ready() -> None:
    item = _request()
    approval_service.approve(
        item.id,
        ApprovalDecision(actor='supervisor', role=ActorRole.approver, note='approved'),
    )
    result = resolution_status('s1', 'w1', 'brano')
    assert result['approved'] == 1
    assert result['resume_ready'] is True
    assert result['items'][0]['approved_by'] == 'supervisor'


def test_resolution_status_is_scoped() -> None:
    _request()
    result = resolution_status('other', 'w1', 'brano')
    assert result['count'] == 0
    assert result['resume_ready'] is False
