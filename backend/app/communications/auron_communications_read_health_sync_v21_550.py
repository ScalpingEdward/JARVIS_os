from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.communications.auron_communications_adapter_onboarding_v21_548 import (
    CommunicationsAdapterOnboardingPolicy,
    CommunicationsProviderBoundary,
)
from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsConversation,
    CommunicationsRegistryStateStore,
)


class CommunicationsReadSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConversationSnapshot:
    provider_conversation_ref: str
    subject: str
    participants: tuple[str, ...]
    state: str
    unread_count: int
    last_message_at: str | None


@dataclass(frozen=True)
class ProviderMessageSnapshot:
    provider_message_ref: str
    provider_conversation_ref: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body_text: str
    occurred_at: str
    inbound: bool = True


@dataclass(frozen=True)
class ProviderReadSnapshot:
    account_id: str
    channel_id: str
    conversations: tuple[ProviderConversationSnapshot, ...]
    messages: tuple[ProviderMessageSnapshot, ...]
    observed_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class CommunicationsSyncResult:
    account_id: str
    channel_id: str
    conversations_synced: int
    messages_synced: int
    state: str
    blockers: tuple[str, ...]
    observed_at: str
    external_calls_made: int
    outbound_execution_enabled: bool = False


class CommunicationsReadSource(Protocol):
    def read_snapshot(self, account_ref: str, channel_address: str) -> ProviderReadSnapshot: ...


class DisabledCommunicationsReadSource:
    def read_snapshot(self, account_ref: str, channel_address: str) -> ProviderReadSnapshot:
        raise CommunicationsReadSyncError('communications read source is disabled')


class InMemoryCommunicationsReadSource:
    def __init__(self, snapshots: dict[tuple[str, str], ProviderReadSnapshot]) -> None:
        self.snapshots = snapshots

    def read_snapshot(self, account_ref: str, channel_address: str) -> ProviderReadSnapshot:
        key = (account_ref, channel_address.lower())
        if key not in self.snapshots:
            raise CommunicationsReadSyncError('provider snapshot not found')
        return self.snapshots[key]


class CommunicationsReadHealthSyncService:
    """D3 read-only provider sync into the normalized D2 communications state."""

    def __init__(self, store: CommunicationsRegistryStateStore,
                 onboarding_provider: CommunicationsProviderBoundary,
                 read_source: CommunicationsReadSource | None = None) -> None:
        self.store = store
        self.onboarding_provider = onboarding_provider
        self.read_source = read_source or DisabledCommunicationsReadSource()
        self.onboarding = CommunicationsAdapterOnboardingPolicy()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _conversation_id(channel_id: str, provider_ref: str) -> str:
        return f'{channel_id}:provider:{provider_ref}'

    @staticmethod
    def _message_id(channel_id: str, provider_ref: str) -> str:
        return f'{channel_id}:provider-message:{provider_ref}'

    def sync_channel(self, channel_id: str) -> CommunicationsSyncResult:
        channel = self.store.get_channel(channel_id)
        if channel is None:
            raise CommunicationsReadSyncError('communications channel not found')
        account = self.store.get_account(channel.account_id)
        if account is None:
            raise CommunicationsReadSyncError('communications account not found')

        blockers: list[str] = []
        onboarding = self.onboarding.evaluate(self.onboarding_provider)
        external_calls = onboarding.external_calls_made
        if not onboarding.accepted or onboarding.allowed_mode != 'read-only':
            blockers.append('provider-not-read-only-certified')
        descriptor = self.onboarding_provider.descriptor()
        if descriptor.provider_id != account.provider_id:
            blockers.append('provider-account-mismatch')
        if account.status != 'active' or channel.status != 'active':
            blockers.append('account-or-channel-not-active')

        if blockers:
            return CommunicationsSyncResult(
                account.account_id, channel.channel_id, 0, 0, 'blocked', tuple(dict.fromkeys(blockers)),
                self._now(), external_calls, False,
            )

        try:
            snapshot = self.read_source.read_snapshot(account.provider_account_ref, channel.address)
        except Exception as exc:
            return CommunicationsSyncResult(
                account.account_id, channel.channel_id, 0, 0, 'read-failed',
                ('provider-read-unavailable',), self._now(), external_calls, False,
            )

        external_calls += snapshot.external_calls_made
        if snapshot.account_id != account.account_id or snapshot.channel_id != channel.channel_id:
            return CommunicationsSyncResult(
                account.account_id, channel.channel_id, 0, 0, 'blocked',
                ('provider-snapshot-identity-mismatch',), snapshot.observed_at, external_calls, False,
            )

        conversations_synced = 0
        messages_synced = 0
        conversation_map: dict[str, str] = {}
        for item in snapshot.conversations:
            conversation_id = self._conversation_id(channel.channel_id, item.provider_conversation_ref)
            conversation_map[item.provider_conversation_ref] = conversation_id
            existing = self.store.get_conversation(conversation_id)
            normalized = CommunicationsConversation(
                conversation_id=conversation_id,
                channel_id=channel.channel_id,
                provider_conversation_ref=item.provider_conversation_ref,
                subject=item.subject,
                participants=item.participants,
                state=item.state,
                unread_count=item.unread_count,
                last_message_at=item.last_message_at,
                updated_at=snapshot.observed_at,
            )
            self.store.upsert_conversation(normalized)
            conversations_synced += 1

        for item in snapshot.messages:
            conversation_id = conversation_map.get(item.provider_conversation_ref)
            if conversation_id is None:
                blockers.append('message-conversation-not-in-snapshot')
                continue
            message_id = self._message_id(channel.channel_id, item.provider_message_ref)
            existed = self.store.get_message(message_id) is not None
            self.store.add_message(
                message_id=message_id,
                conversation_id=conversation_id,
                provider_message_ref=item.provider_message_ref,
                direction='inbound' if item.inbound else 'outbound-simulated',
                sender=item.sender,
                recipients=item.recipients,
                subject=item.subject,
                body_text=item.body_text,
                state='received' if item.inbound else 'simulated',
                occurred_at=item.occurred_at,
            )
            if not existed:
                messages_synced += 1

        return CommunicationsSyncResult(
            account.account_id,
            channel.channel_id,
            conversations_synced,
            messages_synced,
            'synced-read-only' if not blockers else 'synced-with-blockers',
            tuple(dict.fromkeys(blockers)),
            snapshot.observed_at,
            external_calls,
            False,
        )
