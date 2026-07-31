from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_live_execution_arm_gate_v21_269 import LiveExecutionArmRequest, arm
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
                'session_id': 'v269',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='live execution arm gate test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _confirmation(record, **overrides):
    data = {
        'approval_id': str(record.id),
        'confirmed_by': 'brano',
        'session_id': 'v269',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'preview_adapter': 'github-remote-adapter',
        'execution_domain': 'code-remote',
        'predicted_risk': 'high',
        'operator_confirmed': True,
    }
    data.update(overrides)
    return data


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v269',
        workspace_id='demo',
        operator_id='brano',
        confirmation_receipt=_confirmation(record),
        arm=True,
        emergency_stop_clear=True,
        runtime_healthy=True,
        adapter_ready=True,
        credentials_valid=True,
        policy_still_valid=True,
    )
    data.update(overrides)
    return LiveExecutionArmRequest(**data)


def test_arm_gate_creates_arm_receipt_without_execution() -> None:
    record = _consumed()
    result = arm(_payload(record))
    assert result['state'] == 'execution-armed'
    assert result['arm_receipt']['armed'] is True
    assert result['live_execution_enabled'] is False
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'single-use-execution-token'


def test_invalid_confirmation_receipt_is_blocked() -> None:
    record = _consumed()
    payload = _payload(record, confirmation_receipt=_confirmation(record, operator_confirmed=False))
    result = arm(payload)
    assert result['state'] == 'arming-blocked'
    assert 'operator_confirmed' in result['blockers']
    assert result['next_gate'] == 'execution-preview-review'


def test_failed_safety_readiness_routes_to_remediation() -> None:
    record = _consumed()
    result = arm(_payload(record, emergency_stop_clear=False))
    assert result['state'] == 'arming-blocked'
    assert 'emergency_stop_clear' in result['blockers']
    assert result['next_gate'] == 'preflight-remediation'
    assert result['execution_performed'] is False


def test_operator_can_decline_arming() -> None:
    record = _consumed()
    result = arm(_payload(record, arm=False))
    assert result['state'] == 'arming-declined'
    assert result['live_execution_enabled'] is False
    assert result['execution_performed'] is False


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.269/arm', json=_payload(record, session_id='wrong').model_dump(mode='json'))
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.269/command-center')
    assert response.status_code == 200
    assert 'v21.269' in response.text
    assert 'AURON LIVE EXECUTION ARM GATE COMMAND CENTER' in response.text
