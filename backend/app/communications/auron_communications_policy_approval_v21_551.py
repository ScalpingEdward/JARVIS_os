from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.communications.auron_communications_registry_state_v21_549 import CommunicationsRegistryStateStore

IntentKind = Literal['new-message', 'reply']
IntentState = Literal['draft', 'pending-approval', 'approved-for-simulation', 'revoked', 'stale', 'blocked']


class CommunicationsApprovalError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsOutboundIntent:
    intent_id: str
    channel_id: str
    conversation_id: str | None
    kind: IntentKind
    recipients: tuple[str, ...]
    subject: str
    body_text: str
    content_hash: str
    state: IntentState
    created_by: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CommunicationsApproval:
    approval_id: str
    intent_id: str
    content_hash: str
    approved_by: str
    reason: str
    approved_at: str
    revoked: bool


@dataclass(frozen=True)
class CommunicationsApprovalDecision:
    intent_id: str
    state: str
    blockers: tuple[str, ...]
    approval_id: str | None
    outbound_execution_enabled: bool = False
    external_calls_made: int = 0


class CommunicationsPolicyApprovalService:
    """D4 policy/approval boundary for communications drafts and outbound intents.

    Approval is bound to the exact content hash. Any edit after approval invalidates
    the approval. D4 can advance only to simulation readiness and contains no send API.
    """

    def __init__(self, db_path: str | Path, store: CommunicationsRegistryStateStore) -> None:
        self.db_path = str(db_path)
        self.store = store
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.strip().lower() for v in values if v.strip()))

    @staticmethod
    def _hash(channel_id: str, conversation_id: str | None, kind: str,
              recipients: tuple[str, ...], subject: str, body_text: str) -> str:
        payload = json.dumps({
            'channel_id': channel_id,
            'conversation_id': conversation_id,
            'kind': kind,
            'recipients': recipients,
            'subject': subject,
            'body_text': body_text,
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_outbound_intents (
                intent_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, conversation_id TEXT,
                kind TEXT NOT NULL, recipients_json TEXT NOT NULL, subject TEXT NOT NULL,
                body_text TEXT NOT NULL, content_hash TEXT NOT NULL, state TEXT NOT NULL,
                created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_intent_approvals (
                approval_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL,
                content_hash TEXT NOT NULL, approved_by TEXT NOT NULL, reason TEXT NOT NULL,
                approved_at TEXT NOT NULL, revoked INTEGER NOT NULL,
                FOREIGN KEY(intent_id) REFERENCES communications_outbound_intents(intent_id))''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comms_intent_state ON communications_outbound_intents(state, updated_at)')

    def create_or_update_draft(self, *, intent_id: str, channel_id: str,
                               recipients: tuple[str, ...], subject: str, body_text: str,
                               created_by: str, kind: IntentKind = 'new-message',
                               conversation_id: str | None = None) -> CommunicationsOutboundIntent:
        channel = self.store.get_channel(channel_id)
        if channel is None or channel.status != 'active':
            raise CommunicationsApprovalError('active communications channel required')
        if kind == 'reply':
            if not conversation_id or self.store.get_conversation(conversation_id) is None:
                raise CommunicationsApprovalError('reply requires an existing conversation')
        if not intent_id.strip() or not created_by.strip():
            raise CommunicationsApprovalError('intent id and creator are required')
        normalized = self._normalize(recipients)
        if not normalized:
            raise CommunicationsApprovalError('at least one recipient is required')
        content_hash = self._hash(channel_id, conversation_id, kind, normalized, subject, body_text)
        now = self._now()
        existing = self.get_intent(intent_id)
        created_at = existing.created_at if existing else now
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_outbound_intents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(intent_id) DO UPDATE SET channel_id=excluded.channel_id,
                conversation_id=excluded.conversation_id,kind=excluded.kind,
                recipients_json=excluded.recipients_json,subject=excluded.subject,
                body_text=excluded.body_text,content_hash=excluded.content_hash,
                state='draft',updated_at=excluded.updated_at''',
                (intent_id, channel_id, conversation_id, kind, json.dumps(normalized), subject,
                 body_text, content_hash, 'draft', created_by, created_at, now))
        return self.get_intent(intent_id)

    def request_approval(self, intent_id: str) -> CommunicationsOutboundIntent:
        intent = self._require_intent(intent_id)
        if intent.state not in {'draft', 'stale', 'revoked', 'blocked'}:
            return intent
        return self._set_state(intent_id, 'pending-approval')

    def approve(self, intent_id: str, *, approved_by: str, reason: str) -> CommunicationsApproval:
        intent = self._require_intent(intent_id)
        if intent.state != 'pending-approval':
            raise CommunicationsApprovalError('intent must be pending approval')
        if not approved_by.strip() or not reason.strip():
            raise CommunicationsApprovalError('approver and reason are required')
        approval_id = 'approval:' + hashlib.sha256(f'{intent.intent_id}:{intent.content_hash}'.encode()).hexdigest()[:24]
        now = self._now()
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_intent_approvals VALUES (?,?,?,?,?,?,0)
                ON CONFLICT(approval_id) DO UPDATE SET approved_by=excluded.approved_by,
                reason=excluded.reason,approved_at=excluded.approved_at,revoked=0''',
                (approval_id, intent.intent_id, intent.content_hash, approved_by.strip(), reason.strip(), now))
            conn.execute("UPDATE communications_outbound_intents SET state='approved-for-simulation',updated_at=? WHERE intent_id=?",
                         (now, intent.intent_id))
        approval = self.get_approval(approval_id)
        if approval is None:
            raise CommunicationsApprovalError('approval persistence failed')
        return approval

    def revoke(self, approval_id: str) -> CommunicationsApproval:
        approval = self.get_approval(approval_id)
        if approval is None:
            raise CommunicationsApprovalError('approval not found')
        with self._connect() as conn:
            conn.execute('UPDATE communications_intent_approvals SET revoked=1 WHERE approval_id=?', (approval_id,))
            conn.execute("UPDATE communications_outbound_intents SET state='revoked',updated_at=? WHERE intent_id=?",
                         (self._now(), approval.intent_id))
        return self.get_approval(approval_id)

    def evaluate(self, intent_id: str) -> CommunicationsApprovalDecision:
        intent = self._require_intent(intent_id)
        blockers: list[str] = []
        channel = self.store.get_channel(intent.channel_id)
        if channel is None or channel.status != 'active':
            blockers.append('channel-not-active')
        if intent.kind == 'reply':
            if not intent.conversation_id or self.store.get_conversation(intent.conversation_id) is None:
                blockers.append('reply-conversation-missing')
        approval = self.get_current_approval(intent.intent_id)
        if approval is None:
            blockers.append('approval-required')
        else:
            if approval.revoked:
                blockers.append('approval-revoked')
            if approval.content_hash != intent.content_hash:
                blockers.append('approval-stale')
        if intent.state != 'approved-for-simulation':
            blockers.append('intent-not-approved-for-simulation')
        state = 'ready-for-simulation' if not blockers else 'blocked'
        return CommunicationsApprovalDecision(
            intent_id=intent.intent_id,
            state=state,
            blockers=tuple(dict.fromkeys(blockers)),
            approval_id=approval.approval_id if approval else None,
            outbound_execution_enabled=False,
            external_calls_made=0,
        )

    def get_intent(self, intent_id: str) -> CommunicationsOutboundIntent | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_outbound_intents WHERE intent_id=?', (intent_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['recipients'] = tuple(json.loads(data.pop('recipients_json')))
        return CommunicationsOutboundIntent(**data)

    def get_approval(self, approval_id: str) -> CommunicationsApproval | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_intent_approvals WHERE approval_id=?', (approval_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['revoked'] = bool(data['revoked'])
        return CommunicationsApproval(**data)

    def get_current_approval(self, intent_id: str) -> CommunicationsApproval | None:
        with self._connect() as conn:
            row = conn.execute('''SELECT approval_id FROM communications_intent_approvals
                                  WHERE intent_id=? ORDER BY approved_at DESC LIMIT 1''', (intent_id,)).fetchone()
        return self.get_approval(row['approval_id']) if row else None

    def _require_intent(self, intent_id: str) -> CommunicationsOutboundIntent:
        intent = self.get_intent(intent_id)
        if intent is None:
            raise CommunicationsApprovalError('outbound intent not found')
        return intent

    def _set_state(self, intent_id: str, state: IntentState) -> CommunicationsOutboundIntent:
        with self._connect() as conn:
            conn.execute('UPDATE communications_outbound_intents SET state=?,updated_at=? WHERE intent_id=?',
                         (state, self._now(), intent_id))
        return self._require_intent(intent_id)
