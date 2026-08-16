from pathlib import Path

from app.communications.auron_communications_adapter_onboarding_v21_548 import (
    CommunicationsProviderDescriptor,
    CommunicationsProviderHealth,
    DisabledCommunicationsProviderBoundary,
)
from app.communications.auron_communications_read_health_sync_v21_550 import (
    CommunicationsReadHealthSyncService,
    InMemoryCommunicationsReadSource,
    ProviderConversationSnapshot,
    ProviderMessageSnapshot,
    ProviderReadSnapshot,
)
from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsAccount,
    CommunicationsChannel,
    CommunicationsRegistryStateStore,
)
from app.core.auron_integration_readiness_v21_550 import get_integration_readiness


class HealthyProvider:
    def descriptor(self):
        return CommunicationsProviderDescriptor(
            provider_id='gmail-like',
            display_name='Gmail-like',
            capabilities=('identity', 'health', 'read', 'draft'),
            supported_modes=('simulation', 'read-only'),
            requires_operator_approval=True,
            supports_idempotency=True,
            supports_reconciliation=True,
        )

    def read_health(self):
        return CommunicationsProviderHealth(
            provider_id='gmail-like',
            reachable=True,
            authenticated=True,
            identity_verified=True,
            permissions_verified=True,
            observed_at='2026-08-16T18:00:00+00:00',
            external_calls_made=1,
        )


def stack(tmp_path: Path):
    store = CommunicationsRegistryStateStore(tmp_path / 'communications.sqlite3')
    store.upsert_account(CommunicationsAccount('acc-1', 'gmail-like', 'provider-acc-1', 'Inbox'))
    store.upsert_channel(CommunicationsChannel('ch-1', 'acc-1', 'email', 'me@example.com'))
    snapshot = ProviderReadSnapshot(
        account_id='acc-1',
        channel_id='ch-1',
        conversations=(
            ProviderConversationSnapshot(
                'thread-1', 'Question', ('me@example.com', 'other@example.com'),
                'open', 1, '2026-08-16T18:05:00+00:00'
            ),
        ),
        messages=(
            ProviderMessageSnapshot(
                'msg-1', 'thread-1', 'other@example.com', ('me@example.com',),
                'Question', 'Hello', '2026-08-16T18:05:00+00:00', True
            ),
        ),
        observed_at='2026-08-16T18:06:00+00:00',
        external_calls_made=1,
    )
    source = InMemoryCommunicationsReadSource({('provider-acc-1', 'me@example.com'): snapshot})
    return store, CommunicationsReadHealthSyncService(store, HealthyProvider(), source)


def test_read_only_sync_normalizes_provider_state(tmp_path):
    store, service = stack(tmp_path)
    result = service.sync_channel('ch-1')
    assert result.state == 'synced-read-only'
    assert result.conversations_synced == 1
    assert result.messages_synced == 1
    assert result.outbound_execution_enabled is False
    assert result.external_calls_made == 2
    conversations = store.list_conversations(channel_id='ch-1')
    assert len(conversations) == 1
    messages = store.list_messages(conversations[0].conversation_id)
    assert len(messages) == 1
    assert messages[0].direction == 'inbound'
    assert messages[0].state == 'received'


def test_repeated_sync_is_message_idempotent(tmp_path):
    store, service = stack(tmp_path)
    first = service.sync_channel('ch-1')
    second = service.sync_channel('ch-1')
    assert first.messages_synced == 1
    assert second.messages_synced == 0
    conversation = store.list_conversations(channel_id='ch-1')[0]
    assert len(store.list_messages(conversation.conversation_id)) == 1


def test_disabled_provider_fails_closed_before_read(tmp_path):
    store, _ = stack(tmp_path)
    service = CommunicationsReadHealthSyncService(store, DisabledCommunicationsProviderBoundary('gmail-like'))
    result = service.sync_channel('ch-1')
    assert result.state == 'blocked'
    assert 'provider-not-read-only-certified' in result.blockers
    assert result.outbound_execution_enabled is False
    assert result.external_calls_made == 0


def test_provider_identity_mismatch_blocks(tmp_path):
    store, service = stack(tmp_path)

    class WrongProvider(HealthyProvider):
        def descriptor(self):
            d = super().descriptor()
            return CommunicationsProviderDescriptor(
                provider_id='wrong-provider', display_name=d.display_name,
                capabilities=d.capabilities, supported_modes=d.supported_modes,
                requires_operator_approval=d.requires_operator_approval,
                supports_idempotency=d.supports_idempotency,
                supports_reconciliation=d.supports_reconciliation,
            )

        def read_health(self):
            return CommunicationsProviderHealth(
                provider_id='wrong-provider', reachable=True, authenticated=True,
                identity_verified=True, permissions_verified=True,
                observed_at='2026-08-16T18:00:00+00:00', external_calls_made=1,
            )

    blocked = CommunicationsReadHealthSyncService(store, WrongProvider(), service.read_source).sync_channel('ch-1')
    assert blocked.state == 'blocked'
    assert 'provider-account-mismatch' in blocked.blockers


def test_d3_readiness_advances_to_policy_boundary():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.550'
    assert readiness['next_item'] == 'D4-communications-policy-approval-boundary'
    assert readiness['communications_outbound_enabled'] is False
    assert readiness['external_calls_made'] == 0
