from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_adapter_preflight_readiness_v21_265 import AdapterPreflightRequest, run_preflight
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
                'session_id': 'v265',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='preflight readiness test',
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
        session_id='v265',
        workspace_id='demo',
        operator_id='brano',
        adapter_registered=True,
        runtime_available=True,
        credentials_present=True,
        operator_enabled=True,
    )
    data.update(overrides)
    return AdapterPreflightRequest(**data)


def test_mt5_preflight_passes_only_with_all_required_evidence() -> None:
    result = run_preflight(_payload(_consumed('auron.mt5.trade.execute')))
    assert result['state'] == 'preflight-passed'
    assert result['adapter'] == 'mt5-protected-adapter'
    assert result['ready_for_invoke'] is True
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'controlled-adapter-invocation'


def test_missing_credentials_blocks_protected_adapter() -> None:
    result = run_preflight(_payload(_consumed('auron.github.repository.update'), credentials_present=False))
    assert result['state'] == 'preflight-blocked'
    assert 'credentials_present' in result['blockers']
    assert result['ready_for_invoke'] is False
    assert result['next_gate'] == 'preflight-remediation'


def test_generic_adapter_does_not_require_credentials() -> None:
    result = run_preflight(_payload(_consumed('auron.execute.high_risk'), credentials_present=False))
    assert result['adapter'] == 'governed-tool-adapter'
    assert result['checks']['credentials_present'] is True
    assert result['preflight_passed'] is True


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed('auron.github.repository.update')
    client = TestClient(app)
    payload = _payload(record, session_id='wrong').model_dump(mode='json')
    response = client.post('/auron/demo1/v21.265/run-preflight', json=payload)
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.265/command-center')
    assert response.status_code == 200
    assert 'v21.265' in response.text
    assert 'AURON ADAPTER PREFLIGHT READINESS COMMAND CENTER' in response.text
