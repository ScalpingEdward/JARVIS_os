from pathlib import Path

from app.communications.auron_communications_controlled_execution_v21_553 import ControlledCommunicationsExecutionService
from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_registry_state_v21_549 import CommunicationsAccount, CommunicationsChannel, CommunicationsRegistryStateStore
from app.communications.auron_communications_simulation_dry_run_v21_552 import CommunicationsSimulationDryRunService
from app.core.auron_integration_readiness_v21_553 import get_integration_readiness


def stack(tmp_path: Path):
    store = CommunicationsRegistryStateStore(tmp_path / 'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1', 'gmail-like', 'provider-acc-1', 'Inbox'))
    store.upsert_channel(CommunicationsChannel('ch-1', 'acc-1', 'email', 'me@example.com'))
    approvals = CommunicationsPolicyApprovalService(tmp_path / 'approval.sqlite3', store)
    approvals.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Approved body', created_by='operator'
    )
    approvals.request_approval('intent-1')
    approvals.approve('intent-1', approved_by='operator', reason='checked')
    dryrun = CommunicationsSimulationDryRunService(tmp_path / 'dryrun.sqlite3', store, approvals)
    plan = dryrun.create_plan('intent-1')
    result = dryrun.simulate(plan.plan_id)
    assert result.state == 'simulated-success'
    execution = ControlledCommunicationsExecutionService(tmp_path / 'execution.sqlite3', store, approvals, dryrun)
    return approvals, plan, execution


def test_missing_execution_scope_fails_closed(tmp_path):
    _, plan, execution = stack(tmp_path)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'execution-scope-missing' in decision.blockers
    assert decision.external_calls_made == 0


def test_scope_requires_operator_and_clear_kill_switch(tmp_path):
    _, plan, execution = stack(tmp_path)
    execution.configure_scope('ch-1', enabled=True, operator_enabled=False, kill_switch=True)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'operator-enablement-required' in decision.blockers
    assert 'execution-kill-switch-active' in decision.blockers


def test_ready_scope_reaches_boundary_but_default_writer_is_disabled(tmp_path):
    _, plan, execution = stack(tmp_path)
    execution.configure_scope('ch-1', enabled=True, operator_enabled=True, kill_switch=False)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'ready-for-controlled-execution'
    result = execution.execute(plan.plan_id)
    assert result.state == 'provider-write-disabled'
    assert result.external_calls_made == 0


def test_execution_decision_is_idempotent(tmp_path):
    _, plan, execution = stack(tmp_path)
    first = execution.evaluate(plan.plan_id)
    second = execution.evaluate(plan.plan_id)
    assert first.execution_id == second.execution_id
    assert first == second


def test_edit_after_dry_run_blocks_execution(tmp_path):
    approvals, plan, execution = stack(tmp_path)
    approvals.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Changed after simulation', created_by='operator'
    )
    execution.configure_scope('ch-1', enabled=True, operator_enabled=True, kill_switch=False)
    decision = execution.evaluate(plan.plan_id)
    assert decision.state == 'blocked'
    assert 'current-d4-approval-required' in decision.blockers
    assert 'content-hash-changed' in decision.blockers


def test_d6_readiness_advances_to_d7_without_default_outbound():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.553'
    assert readiness['next_item'] == 'D7-communications-reconciliation-retries'
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['communications_provider_write_available'] is False
    assert readiness['external_calls_made'] == 0
