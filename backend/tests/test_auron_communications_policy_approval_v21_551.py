from pathlib import Path

from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsAccount,
    CommunicationsChannel,
    CommunicationsConversation,
    CommunicationsRegistryStateStore,
)
from app.core.auron_integration_readiness_v21_551 import get_integration_readiness


def stack(tmp_path: Path):
    store = CommunicationsRegistryStateStore(tmp_path / 'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1', 'gmail-like', 'provider-acc-1', 'Inbox'))
    store.upsert_channel(CommunicationsChannel('ch-1', 'acc-1', 'email', 'me@example.com'))
    store.upsert_conversation(CommunicationsConversation(
        'conv-1', 'ch-1', 'thread-1', 'Question', ('me@example.com','other@example.com'),
        'open', 0, None, ''
    ))
    service = CommunicationsPolicyApprovalService(tmp_path / 'approval.sqlite3', store)
    return store, service


def test_new_message_requires_explicit_approval(tmp_path):
    _, service = stack(tmp_path)
    service.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Draft body', created_by='operator'
    )
    decision = service.evaluate('intent-1')
    assert decision.state == 'blocked'
    assert 'approval-required' in decision.blockers
    assert decision.outbound_execution_enabled is False


def test_approved_intent_reaches_simulation_only(tmp_path):
    _, service = stack(tmp_path)
    service.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Draft body', created_by='operator'
    )
    service.request_approval('intent-1')
    approval = service.approve('intent-1', approved_by='operator', reason='checked')
    decision = service.evaluate('intent-1')
    assert decision.state == 'ready-for-simulation'
    assert decision.approval_id == approval.approval_id
    assert decision.outbound_execution_enabled is False
    assert decision.external_calls_made == 0


def test_edit_after_approval_invalidates_authorization(tmp_path):
    _, service = stack(tmp_path)
    service.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Draft body', created_by='operator'
    )
    service.request_approval('intent-1')
    service.approve('intent-1', approved_by='operator', reason='checked')
    service.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Changed body', created_by='operator'
    )
    decision = service.evaluate('intent-1')
    assert decision.state == 'blocked'
    assert 'approval-stale' in decision.blockers


def test_reply_requires_existing_conversation(tmp_path):
    _, service = stack(tmp_path)
    service.create_or_update_draft(
        intent_id='reply-1', channel_id='ch-1', conversation_id='conv-1', kind='reply',
        recipients=('other@example.com',), subject='Re: Question', body_text='Reply', created_by='operator'
    )
    service.request_approval('reply-1')
    service.approve('reply-1', approved_by='operator', reason='checked')
    assert service.evaluate('reply-1').state == 'ready-for-simulation'


def test_revocation_blocks_simulation(tmp_path):
    _, service = stack(tmp_path)
    service.create_or_update_draft(
        intent_id='intent-1', channel_id='ch-1', recipients=('other@example.com',),
        subject='Hello', body_text='Draft body', created_by='operator'
    )
    service.request_approval('intent-1')
    approval = service.approve('intent-1', approved_by='operator', reason='checked')
    service.revoke(approval.approval_id)
    decision = service.evaluate('intent-1')
    assert decision.state == 'blocked'
    assert 'approval-revoked' in decision.blockers


def test_d4_readiness_advances_to_d5_without_outbound():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.551'
    assert readiness['next_item'] == 'D5-communications-simulation-dry-run'
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['external_calls_made'] == 0
