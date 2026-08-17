from pathlib import Path

from app.communications.auron_communications_command_centre_v21_555 import CommunicationsCommandCentre
from app.communications.auron_communications_controlled_execution_v21_553 import ControlledCommunicationsExecutionService
from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_reconciliation_retries_v21_554 import CommunicationsReconciliationRetryService
from app.communications.auron_communications_registry_state_v21_549 import CommunicationsAccount, CommunicationsChannel, CommunicationsConversation, CommunicationsRegistryStateStore
from app.communications.auron_communications_simulation_dry_run_v21_552 import CommunicationsSimulationDryRunService
from app.core.auron_integration_readiness_v21_555 import get_integration_readiness


def stack(tmp_path: Path):
    store = CommunicationsRegistryStateStore(tmp_path/'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1','gmail-like','provider-acc-1','Inbox'))
    store.upsert_channel(CommunicationsChannel('ch-1','acc-1','email','me@example.com'))
    store.upsert_conversation(CommunicationsConversation('conv-1','ch-1','thread-1','Question',('me@example.com','other@example.com'),'open',2,None,''))
    approvals = CommunicationsPolicyApprovalService(tmp_path/'approval.sqlite3', store)
    approvals.create_or_update_draft(intent_id='intent-1',channel_id='ch-1',recipients=('other@example.com',),subject='Hello',body_text='Body',created_by='operator')
    approvals.request_approval('intent-1')
    approvals.approve('intent-1',approved_by='operator',reason='checked')
    dryrun = CommunicationsSimulationDryRunService(tmp_path/'dryrun.sqlite3', store, approvals)
    plan = dryrun.create_plan('intent-1')
    dryrun.simulate(plan.plan_id)
    execution = ControlledCommunicationsExecutionService(tmp_path/'execution.sqlite3', store, approvals, dryrun)
    reconciliation = CommunicationsReconciliationRetryService(tmp_path/'reconciliation.sqlite3', execution)
    centre = CommunicationsCommandCentre(tmp_path/'command-centre.sqlite3', store, approvals, dryrun, execution, reconciliation)
    return centre, execution


def test_snapshot_exposes_operational_workspace(tmp_path):
    centre, _ = stack(tmp_path)
    snapshot = centre.snapshot()
    assert snapshot['workspace'] == 'communications'
    assert snapshot['command_field_enabled'] is True
    assert len(snapshot['accounts']) == 1
    assert len(snapshot['channels']) == 1
    assert len(snapshot['conversations']) == 1
    assert snapshot['unread_total'] == 2
    assert len(snapshot['intents']) == 1
    assert len(snapshot['approvals']) == 1
    assert len(snapshot['simulations']) == 1
    assert snapshot['outbound_enabled_by_default'] is False


def test_kill_switch_control_is_fail_closed_and_preserves_scope(tmp_path):
    centre, execution = stack(tmp_path)
    execution.configure_scope('ch-1', enabled=True, operator_enabled=True, kill_switch=False)
    updated = centre.set_channel_kill_switch('ch-1', active=True)
    assert updated['enabled'] is True
    assert updated['operator_enabled'] is True
    assert updated['kill_switch'] is True


def test_missing_scope_kill_switch_defaults_execution_disabled(tmp_path):
    centre, _ = stack(tmp_path)
    updated = centre.set_channel_kill_switch('ch-1', active=True)
    assert updated['enabled'] is False
    assert updated['operator_enabled'] is False
    assert updated['kill_switch'] is True


def test_command_field_is_persistent_but_does_not_execute(tmp_path):
    centre, _ = stack(tmp_path)
    entry = centre.record_command('draft a reply to the latest message', actor='operator')
    assert entry.state == 'recorded-not-executed'
    assert centre.list_commands()[0].command_text == 'draft a reply to the latest message'


def test_d8_marks_vertical_architecture_complete_without_live_default():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.555'
    assert readiness['communications_vertical_architecture_complete'] is True
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['communications_provider_write_available'] is False
    assert readiness['next_item'] == 'D9-next-vertical-selection'
