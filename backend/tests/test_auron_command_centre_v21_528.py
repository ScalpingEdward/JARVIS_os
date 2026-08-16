from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_command_centre_v21_528 import router
from app.core.auron_command_centre_v21_528 import CommandCentreService, CommandCentreStore
from app.core.auron_execution_ledger_v21_526 import ExecutionAuditLedger
from app.core.auron_integration_readiness_v21_528 import get_integration_readiness
from app.core.auron_policy_gate_v21_527 import CentralPolicyGate


def service(tmp_path: Path) -> CommandCentreService:
    return CommandCentreService(
        CommandCentreStore(tmp_path / 'centre.sqlite3'),
        ExecutionAuditLedger(tmp_path / 'ledger.sqlite3'),
        CentralPolicyGate(),
    )


def test_command_field_persists_non_executing_commands(tmp_path: Path) -> None:
    centre = service(tmp_path)
    record = centre.store.submit_command('show trading accounts', 'operator')
    assert record.state == 'received-non-executing'
    assert centre.store.recent_commands()[0].text == 'show trading accounts'
    snapshot = centre.snapshot()
    assert snapshot['command_input_available'] is True
    assert snapshot['command_execution_enabled'] is False
    assert snapshot['external_calls_made'] == 0


def test_approval_workflow_is_persistent_and_idempotent_after_decision(tmp_path: Path) -> None:
    centre = service(tmp_path)
    approval = centre.store.request_approval('req-1', 'trading', 'simulate order', 'operator')
    assert approval.state == 'pending'
    decided = centre.store.decide_approval(approval.approval_id, 'approved', 'operator')
    replay = centre.store.decide_approval(approval.approval_id, 'rejected', 'other')
    assert decided.state == 'approved'
    assert replay.state == 'approved'
    assert centre.store.pending_approvals() == []


def test_snapshot_surfaces_policy_readiness_and_audit(tmp_path: Path) -> None:
    centre = service(tmp_path)
    snapshot = centre.snapshot()
    assert 'readiness' in snapshot
    assert 'policy' in snapshot
    assert snapshot['audit_timeline'] == []
    assert snapshot['pending_approvals'] == []
    assert snapshot['external_calls_made'] == 0


def test_operational_ui_preserves_textarea_and_backend_sections() -> None:
    app = FastAPI(); app.include_router(router)
    response = TestClient(app).get('/auron/command-centre/v21.528/ui')
    assert response.status_code == 200
    html = response.text
    assert '<textarea id="cmd"' in html
    assert 'Pending approvals' in html
    assert 'Audit timeline' in html
    assert 'provider execution disabled in A5' in html


def test_api_command_submission_is_non_executing() -> None:
    app = FastAPI(); app.include_router(router)
    response = TestClient(app).post('/auron/command-centre/v21.528/commands', json={'text':'status','actor':'tester'})
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'command-received-non-executing'
    assert body['external_calls_made'] == 0


def test_a5_advances_exactly_to_a6() -> None:
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.528'
    assert readiness['current_item'] == 'A5-command-centre-real-backend-state-actions-errors-approvals-audit'
    assert readiness['next_item'] == 'A6-end-to-end-integration-harness-cutover-certification'
    assert readiness['core_next_gate'] == 'e2e-cutover-certification'
    assert readiness['command_centre']['command_input_available'] is True
    assert readiness['command_centre']['command_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
