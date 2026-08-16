from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

AccountStatus = Literal['active', 'paused', 'disabled']
ChannelType = Literal['email', 'messaging']
ConversationState = Literal['open', 'waiting', 'closed', 'archived']
MessageDirection = Literal['inbound', 'outbound-draft', 'outbound-simulated']
MessageState = Literal['received', 'draft', 'simulated', 'failed']


class CommunicationsRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsAccount:
    account_id: str
    provider_id: str
    provider_account_ref: str
    display_name: str
    status: AccountStatus = 'active'


@dataclass(frozen=True)
class CommunicationsChannel:
    channel_id: str
    account_id: str
    channel_type: ChannelType
    address: str
    status: AccountStatus = 'active'


@dataclass(frozen=True)
class CommunicationsConversation:
    conversation_id: str
    channel_id: str
    provider_conversation_ref: str | None
    subject: str
    participants: tuple[str, ...]
    state: ConversationState
    unread_count: int
    last_message_at: str | None
    updated_at: str


@dataclass(frozen=True)
class CommunicationsMessage:
    message_id: str
    conversation_id: str
    provider_message_ref: str | None
    direction: MessageDirection
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body_text: str
    state: MessageState
    integrity_hash: str
    occurred_at: str
    created_at: str
    external_calls_made: int = 0


class CommunicationsRegistryStateStore:
    """D2 persistent account/channel registry and normalized communications state.

    This layer stores provider-independent account, channel, conversation and message
    state. It contains no provider transport and cannot send or reply to messages.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_accounts (
                account_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                provider_account_ref TEXT NOT NULL,
                display_name TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(provider_id, provider_account_ref)
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_channels (
                channel_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                channel_type TEXT NOT NULL,
                address TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(account_id) REFERENCES communications_accounts(account_id),
                UNIQUE(account_id, channel_type, address)
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_conversations (
                conversation_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                provider_conversation_ref TEXT,
                subject TEXT NOT NULL,
                participants_json TEXT NOT NULL,
                state TEXT NOT NULL,
                unread_count INTEGER NOT NULL,
                last_message_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES communications_channels(channel_id)
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                provider_message_ref TEXT,
                direction TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipients_json TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_text TEXT NOT NULL,
                state TEXT NOT NULL,
                integrity_hash TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES communications_conversations(conversation_id)
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comms_conversation_channel ON communications_conversations(channel_id, updated_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comms_message_conversation ON communications_messages(conversation_id, occurred_at)')

    @staticmethod
    def _normalize_addresses(values: tuple[str, ...]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip().lower()
            if cleaned and cleaned not in seen:
                result.append(cleaned)
                seen.add(cleaned)
        return tuple(result)

    @staticmethod
    def _message_hash(message_id: str, conversation_id: str, direction: str, sender: str,
                      recipients: tuple[str, ...], subject: str, body_text: str,
                      occurred_at: str) -> str:
        payload = json.dumps({
            'message_id': message_id,
            'conversation_id': conversation_id,
            'direction': direction,
            'sender': sender,
            'recipients': recipients,
            'subject': subject,
            'body_text': body_text,
            'occurred_at': occurred_at,
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode()).hexdigest()

    def upsert_account(self, account: CommunicationsAccount) -> CommunicationsAccount:
        if not all(x.strip() for x in (account.account_id, account.provider_id, account.provider_account_ref, account.display_name)):
            raise CommunicationsRegistryError('account id, provider id, provider account ref and display name are required')
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_accounts VALUES (?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET provider_id=excluded.provider_id,
                provider_account_ref=excluded.provider_account_ref,
                display_name=excluded.display_name,status=excluded.status''',
                (account.account_id, account.provider_id, account.provider_account_ref,
                 account.display_name, account.status))
        result = self.get_account(account.account_id)
        if result is None:
            raise CommunicationsRegistryError('account persistence failed')
        return result

    def get_account(self, account_id: str) -> CommunicationsAccount | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_accounts WHERE account_id=?', (account_id,)).fetchone()
        return CommunicationsAccount(**dict(row)) if row else None

    def list_accounts(self) -> tuple[CommunicationsAccount, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM communications_accounts ORDER BY display_name, account_id').fetchall()
        return tuple(CommunicationsAccount(**dict(row)) for row in rows)

    def upsert_channel(self, channel: CommunicationsChannel) -> CommunicationsChannel:
        if self.get_account(channel.account_id) is None:
            raise CommunicationsRegistryError('account must exist before channel registration')
        address = channel.address.strip().lower()
        if not channel.channel_id.strip() or not address:
            raise CommunicationsRegistryError('channel id and address are required')
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_channels VALUES (?,?,?,?,?)
                ON CONFLICT(channel_id) DO UPDATE SET account_id=excluded.account_id,
                channel_type=excluded.channel_type,address=excluded.address,status=excluded.status''',
                (channel.channel_id, channel.account_id, channel.channel_type, address, channel.status))
        result = self.get_channel(channel.channel_id)
        if result is None:
            raise CommunicationsRegistryError('channel persistence failed')
        return result

    def get_channel(self, channel_id: str) -> CommunicationsChannel | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_channels WHERE channel_id=?', (channel_id,)).fetchone()
        return CommunicationsChannel(**dict(row)) if row else None

    def list_channels(self, account_id: str | None = None) -> tuple[CommunicationsChannel, ...]:
        with self._connect() as conn:
            if account_id is None:
                rows = conn.execute('SELECT * FROM communications_channels ORDER BY account_id, channel_id').fetchall()
            else:
                rows = conn.execute('SELECT * FROM communications_channels WHERE account_id=? ORDER BY channel_id', (account_id,)).fetchall()
        return tuple(CommunicationsChannel(**dict(row)) for row in rows)

    def upsert_conversation(self, conversation: CommunicationsConversation) -> CommunicationsConversation:
        if self.get_channel(conversation.channel_id) is None:
            raise CommunicationsRegistryError('channel must exist before conversation registration')
        participants = self._normalize_addresses(tuple(conversation.participants))
        if not conversation.conversation_id.strip() or not participants:
            raise CommunicationsRegistryError('conversation id and at least one participant are required')
        if conversation.unread_count < 0:
            raise CommunicationsRegistryError('unread_count cannot be negative')
        updated_at = conversation.updated_at or self._now()
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_conversations VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(conversation_id) DO UPDATE SET channel_id=excluded.channel_id,
                provider_conversation_ref=excluded.provider_conversation_ref,subject=excluded.subject,
                participants_json=excluded.participants_json,state=excluded.state,
                unread_count=excluded.unread_count,last_message_at=excluded.last_message_at,
                updated_at=excluded.updated_at''',
                (conversation.conversation_id, conversation.channel_id, conversation.provider_conversation_ref,
                 conversation.subject, json.dumps(participants), conversation.state,
                 conversation.unread_count, conversation.last_message_at, updated_at))
        result = self.get_conversation(conversation.conversation_id)
        if result is None:
            raise CommunicationsRegistryError('conversation persistence failed')
        return result

    def get_conversation(self, conversation_id: str) -> CommunicationsConversation | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_conversations WHERE conversation_id=?', (conversation_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['participants'] = tuple(json.loads(data.pop('participants_json')))
        return CommunicationsConversation(**data)

    def list_conversations(self, *, channel_id: str | None = None,
                           state: ConversationState | None = None) -> tuple[CommunicationsConversation, ...]:
        clauses: list[str] = []
        params: list[str] = []
        if channel_id is not None:
            clauses.append('channel_id=?'); params.append(channel_id)
        if state is not None:
            clauses.append('state=?'); params.append(state)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        with self._connect() as conn:
            rows = conn.execute('SELECT conversation_id FROM communications_conversations' + where +
                                ' ORDER BY COALESCE(last_message_at, updated_at) DESC, conversation_id',
                                tuple(params)).fetchall()
        return tuple(self.get_conversation(row['conversation_id']) for row in rows)

    def add_message(self, *, message_id: str, conversation_id: str,
                    provider_message_ref: str | None = None,
                    direction: MessageDirection, sender: str, recipients: tuple[str, ...],
                    subject: str = '', body_text: str = '', state: MessageState,
                    occurred_at: str | None = None) -> CommunicationsMessage:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise CommunicationsRegistryError('conversation must exist before message insertion')
        if not message_id.strip() or not sender.strip():
            raise CommunicationsRegistryError('message id and sender are required')
        normalized_recipients = self._normalize_addresses(tuple(recipients))
        if not normalized_recipients:
            raise CommunicationsRegistryError('at least one recipient is required')
        occurred_at = occurred_at or self._now()
        integrity_hash = self._message_hash(
            message_id, conversation_id, direction, sender.strip().lower(), normalized_recipients,
            subject, body_text, occurred_at,
        )
        existing = self.get_message(message_id)
        if existing is not None:
            if existing.integrity_hash != integrity_hash:
                raise CommunicationsRegistryError('message id collision with different payload')
            return existing
        created_at = self._now()
        with self._connect() as conn:
            conn.execute('INSERT INTO communications_messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                message_id, conversation_id, provider_message_ref, direction, sender.strip().lower(),
                json.dumps(normalized_recipients), subject, body_text, state, integrity_hash,
                occurred_at, created_at,
            ))
            unread_increment = 1 if direction == 'inbound' and state == 'received' else 0
            conn.execute('''UPDATE communications_conversations
                SET last_message_at=?, updated_at=?, unread_count=unread_count+?
                WHERE conversation_id=?''', (occurred_at, created_at, unread_increment, conversation_id))
        result = self.get_message(message_id)
        if result is None:
            raise CommunicationsRegistryError('message persistence failed')
        return result

    def get_message(self, message_id: str) -> CommunicationsMessage | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_messages WHERE message_id=?', (message_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['recipients'] = tuple(json.loads(data.pop('recipients_json')))
        return CommunicationsMessage(**data, external_calls_made=0)

    def list_messages(self, conversation_id: str) -> tuple[CommunicationsMessage, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT message_id FROM communications_messages
                                   WHERE conversation_id=? ORDER BY occurred_at, created_at, message_id''',
                                (conversation_id,)).fetchall()
        return tuple(self.get_message(row['message_id']) for row in rows)

    def mark_conversation_read(self, conversation_id: str) -> CommunicationsConversation:
        if self.get_conversation(conversation_id) is None:
            raise CommunicationsRegistryError('conversation not found')
        with self._connect() as conn:
            conn.execute('UPDATE communications_conversations SET unread_count=0, updated_at=? WHERE conversation_id=?',
                         (self._now(), conversation_id))
        result = self.get_conversation(conversation_id)
        if result is None:
            raise CommunicationsRegistryError('conversation update failed')
        return result

    def snapshot(self) -> dict:
        return {
            'accounts': len(self.list_accounts()),
            'channels': len(self.list_channels()),
            'conversations': len(self.list_conversations()),
            'messages': sum(len(self.list_messages(c.conversation_id)) for c in self.list_conversations()),
            'provider_connected': False,
            'outbound_execution_enabled': False,
            'external_calls_made': 0,
        }
