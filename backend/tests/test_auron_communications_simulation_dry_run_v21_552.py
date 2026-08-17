from pathlib import Path

import pytest

from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsAccount,
    CommunicationsChannel,
    CommunicationsConversation,
    CommunicationsRegistryStateStore,
)
from app.communications.auron_communications_simulation_dry_run_v21_552 import (
    CommunicationsSimulationDryRunService,
    CommunicationsSimulationError,
)
from app.core.auron_integration_readiness_v21_552 import get_integration_readiness


def stack(tmp_path: Path):
    store = CommunicationsRegistryStateStore(tmp_path / 'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1', 'gmail-like', 'provider-acc-1', 'Inbox'))
    store.upsert_channel(CommunicationsChannel('ch-1', 'acc-1', 'email', 'me@example.com'))
    store.upsert_conversation(CommunicationsConversation(
        'conv-1', 'ch-1', 'thread-1', 'Question', ('me@example.com', 'other@example.com'),
        'open', 0, None, ''
    ))
    approvals = CommunicationsPolicyApprovalService(tmp_path / 'approval.sqlite3', store)
    dryrun = CommunicationsSimulationDryRunService(tmp_path / 'dryrun.sqlite3', store, approvals)
    return store, approvals, dryrun


def approve_intent(approvals, *, intent_id='intent-1', body='Draft body', kind='new-message', conversation_id=None):
    approvals.create_or_update_draft(
        intent_id=intent_id,
        channel_id='ch-1',
        conversation_id=conversation_id,
        kind=kind,
        recipients=('other@example.com',),
        subject='Hello' if kind == 'new-message' else 'Re: Question',
        body_text=body,
        created_by='operator',
    )
    approvals.request_approval(intent_id)
    approvals.approve(intent_id, approved_by='operator', reason='checked')


def test_unapproved_intent_cannot_create_dry_run_plan(tmp_path):
    _, approvals, dryrun = stack(tmp_path)
    approvals.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Draft body', created_by='operator'
    )
    with pytest.raises(CommunicationsSimulationError):
        dryrun.create_plan('intent-1')


def test_approved_intent_creates_deterministic_idempotent_plan(tmp_path):
    _, approvals, dryrun = stack(tmp_path)
    approve_intent(approvals)
    first = dryrun.create_plan('intent-1')
    second = dryrun.create_plan('intent-1')
    assert first == second
    assert first.plan_id.startswith('comms-dryrun:')
    assert first.external_calls_made == 0


def test_simulation_renders_exact_payload_without_provider_write(tmp_path):
    _, approvals, dryrun = stack(tmp_path)
    approve_intent(approvals)
    plan = dryrun.create_plan('intent-1')
    result = dryrun.simulate(plan.plan_id)
    assert result.state == 'simulated-success'
    assert result.simulated_sender == 'me@example.com'
    assert result.simulated_recipients == ('other@example.com',)
    assert result.rendered_body == 'Draft body'
    assert result.outbound_execution_enabled is False
    assert result.external_calls_made == 0
    assert dryrun.simulate(plan.plan_id) == result


def test_edit_after_plan_fails_closed_at_simulation(tmp_path):
    _, approvals, dryrun = stack(tmp_path)
    approve_intent(approvals)
    plan = dryrun.create_plan('intent-1')
    approvals.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Changed body', created_by='operator'
    )
    result = dryrun.simulate(plan.plan_id)
    assert result.state == 'blocked'
    assert 'current-d4-approval-required' in result.blockers
    assert 'content-hash-changed' in result.blockers
    assert result.external_calls_made == 0


def test_reply_dry_run_revalidates_conversation_binding(tmp_path):
    _, approvals, dryrun = stack(tmp_path)
    approve_intent(approvals, intent_id='reply-1', kind='reply', conversation_id='conv-1')
    plan = dryrun.create_plan('reply-1')
    result = dryrun.simulate(plan.plan_id)
    assert result.state == 'simulated-success'
    assert result.outbound_execution_enabled is False


def test_d5_readiness_advances_to_d6_without_outbound():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.552'
    assert readiness['next_item'] == 'D6-communications-controlled-execution'
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['communications_provider_write_available'] is False
    assert readiness['external_calls_made'] == 0
