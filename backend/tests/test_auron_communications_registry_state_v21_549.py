from pathlib import Path

import pytest

from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsAccount,
    CommunicationsChannel,
    CommunicationsConversation,
    CommunicationsRegistryError,
    CommunicationsRegistryStateStore,
)
from app.core.auron_integration_readiness_v21_549 import get_integration_readiness


def build_store(tmp_path: Path) -> CommunicationsRegistryStateStore:
    store = CommunicationsRegistryStateStore(tmp_path / 'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1', 'provider-test', 'provider-account-1', 'Primary Inbox'))
    store.upsert_channel(CommunicationsChannel('channel-1', 'acc-1', 'email', 'Owner@Example.com'))
    store.upsert_conversation(CommunicationsConversation(
        conversation_id='conv-1',
        channel_id='channel-1',
        provider_conversation_ref='thread-1',
        subject='Order question',
        participants=('customer@example.com', 'owner@example.com'),
        state='open',
        unread_count=0,
        last_message_at=None,
        updated_at='2026-08-16T18:00:00+00:00',
    ))
    return store


def test_registry_state_persists_across_reopen(tmp_path):
    db = tmp_path / 'communications.sqlite3'
    store = CommunicationsRegistryStateStore(db)
    store.upsert_account(CommunicationsAccount('acc-1', 'provider-test', 'provider-account-1', 'Primary Inbox'))
    store.upsert_channel(CommunicationsChannel('channel-1', 'acc-1', 'email', 'Owner@Example.com'))

    reopened = CommunicationsRegistryStateStore(db)
    assert reopened.get_account('acc-1').display_name == 'Primary Inbox'
    assert reopened.get_channel('channel-1').address == 'owner@example.com'
    assert reopened.snapshot()['outbound_execution_enabled'] is False


def test_inbound_message_normalizes_state_and_increments_unread(tmp_path):
    store = build_store(tmp_path)
    message = store.add_message(
        message_id='msg-1',
        conversation_id='conv-1',
        provider_message_ref='provider-msg-1',
        direction='inbound',
        sender='Customer@Example.com',
        recipients=('Owner@Example.com',),
        subject='Order question',
        body_text='Where is my order?',
        state='received',
        occurred_at='2026-08-16T18:10:00+00:00',
    )
    assert message.sender == 'customer@example.com'
    assert message.recipients == ('owner@example.com',)
    assert len(message.integrity_hash) == 64
    assert message.external_calls_made == 0
    assert store.get_conversation('conv-1').unread_count == 1


def test_duplicate_message_is_idempotent_but_payload_collision_is_blocked(tmp_path):
    store = build_store(tmp_path)
    kwargs = dict(
        message_id='msg-1', conversation_id='conv-1', direction='inbound',
        sender='customer@example.com', recipients=('owner@example.com',),
        subject='Hello', body_text='Same payload', state='received',
        occurred_at='2026-08-16T18:10:00+00:00',
    )
    first = store.add_message(**kwargs)
    second = store.add_message(**kwargs)
    assert first == second
    assert store.get_conversation('conv-1').unread_count == 1

    with pytest.raises(CommunicationsRegistryError):
        store.add_message(**{**kwargs, 'body_text': 'Different payload'})


def test_outbound_state_is_draft_or_simulated_only_no_send_path(tmp_path):
    store = build_store(tmp_path)
    draft = store.add_message(
        message_id='draft-1', conversation_id='conv-1', direction='outbound-draft',
        sender='owner@example.com', recipients=('customer@example.com',),
        subject='Re: Order question', body_text='Draft reply', state='draft',
        occurred_at='2026-08-16T18:12:00+00:00',
    )
    assert draft.direction == 'outbound-draft'
    assert draft.state == 'draft'
    assert store.snapshot()['provider_connected'] is False
    assert store.snapshot()['external_calls_made'] == 0


def test_mark_read_resets_unread_count(tmp_path):
    store = build_store(tmp_path)
    store.add_message(
        message_id='msg-1', conversation_id='conv-1', direction='inbound',
        sender='customer@example.com', recipients=('owner@example.com',),
        body_text='Ping', state='received', occurred_at='2026-08-16T18:10:00+00:00',
    )
    assert store.get_conversation('conv-1').unread_count == 1
    assert store.mark_conversation_read('conv-1').unread_count == 0


def test_d2_readiness_advances_to_d3_without_outbound_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.549'
    assert readiness['next_item'] == 'D3-communications-read-health-integration'
    assert readiness['communications_provider_connected'] is False
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['external_calls_made'] == 0
