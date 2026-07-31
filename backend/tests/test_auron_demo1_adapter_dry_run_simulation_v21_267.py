from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_adapter_dry_run_simulation_v21_267 import DryRunSimulationRequest, simulate
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
                'session_id': 'v267',
                'workspace_id': 'demo',
                'operator_id': 'brano',
            },
            requested_by='brano',
            requester_role=ActorRole.operator,
            risk=RiskLevel.high,
            reason='dry-run simulation test',
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
        session_id='v267',
        workspace_id='demo',
        operator_id='brano',
        adapter_registered=True,
        runtime_available=True,
        credentials_present=True,
        operator_enabled=True,
        dry_run=True,
    )
    data.update(overrides)
    return DryRunSimulationRequest(**data)


def test_financial_simulation_returns_preview_without_execution() -> None:
    result = simulate(_payload(_consumed('auron.mt5.trade.execute')))
    assert result['state'] == 'simulation-complete'
    receipt = result['preview_receipt']
    assert receipt['execution_domain'] == 'financial'
    assert receipt['external_calls_made'] == 0
    assert receipt['mutations_made'] == 0
    assert result['adapter_invoked'] is False
    assert result['execution_performed'] is False
    assert result['next_gate'] == 'execution-preview-review'


def test_github_simulation_stays_non_mutating() -> None:
    result = simulate(_payload(_consumed('auron.github.repository.update')))
    assert result['preview_receipt']['execution_domain'] == 'code-remote'
    assert result['preview_receipt']['external_calls_made'] == 0
    assert result['preview_receipt']['mutations_made'] == 0


def test_live_execution_is_rejected() -> None:
    record = _consumed('auron.mt5.trade.execute')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.267/simulate', json=_payload(record, dry_run=False).model_dump(mode='json'))
    assert response.status_code == 409
    assert 'Live execution is disabled' in response.json()['detail']


def test_failed_readiness_blocks_simulation() -> None:
    result = simulate(_payload(_consumed('auron.github.repository.update'), credentials_present=False))
    assert result['state'] == 'simulation-blocked'
    assert 'credentials_present' in result['blockers']
    assert result['next_gate'] == 'preflight-remediation'


def test_scope_mismatch_is_forbidden() -> None:
    record = _consumed('auron.github.repository.update')
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.267/simulate', json=_payload(record, session_id='wrong').model_dump(mode='json'))
    assert response.status_code == 403


def test_command_center_route_is_registered() -> None:
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.267/command-center')
    assert response.status_code == 200
    assert 'v21.267' in response.text
    assert 'AURON ADAPTER DRY-RUN SIMULATION COMMAND CENTER' in response.text
