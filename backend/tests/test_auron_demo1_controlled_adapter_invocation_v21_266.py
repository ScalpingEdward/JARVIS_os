from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_controlled_adapter_invocation_v21_266 import ControlledInvocationRequest, prepare_invocation
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
                'command': 'execute governed action',
                'session_id': 'v266',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='controlled invocation test',
        )
    )
    token = approval_service.approve(
        record.id,
        ApprovalDecision(actor='approver', role=ActorRole.approver, note='approved'),
    ).confirmation_token
    approval_service.consume(record.id, token, 'brano')
    return record


def _payload(record, **overrides):
    data = dict(
        approval_id=record.id,
        actor='brano',
        session_id='v266',
        workspace_id='demo',
        operator_id='brano',
        adapter_registered=True,
        runtime_available=True,
        credentials_present=True,
        operator_enabled=True,
        dry_run=True,
    )
    data.update(overrides)
    return ControlledInvocationRequest(**data)


def test_ready_adapter_creates_dry_run_envelope_without_invocation() -> None:
    result = prepare_invocation(_payload(_consumed('auron.github.repository.update')))
    assert result['state'] == 'invocation-prepared'
    assert result['invocation_envelope']['mode'] == 'dry-run'
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'adapter-dry-run-simulation'


def test_live_invocation_is_rejected() -> None:
    record = _consumed('auron.mt5.trade.execute')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.266/prepare-invocation', json=_payload(record, dry_run=False).model_dump(mode='json'))
    assert response.status_code == 409
    assert 'Live adapter invocation is not enabled' in response.json()['detail']


def test_failed_preflight_blocks_invocation() -> None:
    result = prepare_invocation(_payload(_consumed('auron.mt5.trade.execute'), credentials_present=False))
    assert result['state'] == 'invocation-blocked'
    assert 'credentials_present' in result['blockers']
    assert result['adapter_invoked'] is False
    assert result['next_gate'] == 'preflight-remediation'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed('auron.github.repository.update')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.266/prepare-invocation', json=_payload(record, session_id='wrong').model_dump(mode='json'))
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.266/command-center')
    assert response.status_code == 200
    assert 'v21.266' in response.text
    assert 'AURON CONTROLLED ADAPTER INVOCATION COMMAND CENTER' in response.text
