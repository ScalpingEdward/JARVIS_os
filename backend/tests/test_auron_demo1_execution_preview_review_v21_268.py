from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_execution_preview_review_v21_268 import ExecutionPreviewReviewRequest, review
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
                'session_id': 'v268',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='execution preview review test',
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
        'actor': 'brano',
        'session_id': 'v268',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'mode': 'dry-run',
        'simulated_steps': ['resolve-repository-target'],
        'predicted_risk': 'high',
        'external_calls_made': 0,
        'mutations_made': 0,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v268',
        workspace_id='demo',
        operator_id='brano',
        preview_receipt=_receipt(record),
        decision='confirm',
        note='looks correct',
    )
    data.update(overrides)
    return ExecutionPreviewReviewRequest(**data)


def test_confirmed_preview_produces_confirmation_receipt_without_execution() -> None:
    record = _consumed()
    result = review(_payload(record))
    assert result['state'] == 'preview-confirmed'
    assert result['confirmation_receipt']['operator_confirmed'] is True
    assert result['execution_performed'] is False
    assert result['adapter_invoked'] is False
    assert result['next_gate'] == 'live-execution-arm-gate'


def test_rejected_preview_routes_to_revision() -> None:
    record = _consumed()
    result = review(_payload(record, decision='reject'))
    assert result['state'] == 'preview-rejected'
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'execution-plan-revision'


def test_tampered_receipt_is_blocked() -> None:
    record = _consumed()
    payload = _payload(record, preview_receipt=_receipt(record, mutations_made=1))
    result = review(payload)
    assert result['state'] == 'preview-review-blocked'
    assert 'mutations_made' in result['blockers']
    assert result['next_gate'] == 'dry-run-simulation'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.268/review', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.268/command-center')
    assert response.status_code == 200
    assert 'v21.268' in response.text
    assert 'AURON EXECUTION PREVIEW REVIEW COMMAND CENTER' in response.text
