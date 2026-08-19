from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryProviderResult


class CommunicationsDraftCanaryAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsDraftCanaryDescriptor:
    adapter_id: str
    vertical: str
    provider_id: str
    allowed_actions: tuple[str, ...]
    side_effect_free: bool
    outbound_send_enabled: bool
    provider_write_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool


class CommunicationsDraftCanaryAdapter:
    """G14 local communications preview/recipient-plan canary adapter.

    Compatible with F2 execution plus F3 result/stop boundaries. It only persists local
    preview/inspection state and never sends outbound messages or opens external transport.
    """

    ADAPTER_ID='communications-draft-canary-v1'
    VERTICAL='communications'
    PROVIDER_ID='communications-local-draft'
    ALLOWED_ACTIONS=('render-message-preview','inspect-recipient-plan')

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path)
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS communications_draft_canary_actions(
                    provider_ref TEXT PRIMARY KEY,vertical TEXT NOT NULL,provider_id TEXT NOT NULL,
                    scope TEXT NOT NULL,action_key TEXT NOT NULL,payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,preview_json TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS communications_draft_canary_stops(
                    activation_id TEXT PRIMARY KEY,reason TEXT NOT NULL,stopped_at TEXT NOT NULL);
            ''')

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def descriptor(self) -> CommunicationsDraftCanaryDescriptor:
        return CommunicationsDraftCanaryDescriptor(
            self.ADAPTER_ID,self.VERTICAL,self.PROVIDER_ID,self.ALLOWED_ACTIONS,
            True,False,False,False,False)

    def execute_canary_action(self, *, vertical: str, provider_id: str, scope: str,
                              action_key: str, payload: dict, idempotency_key: str) -> str:
        if vertical != self.VERTICAL:
            raise CommunicationsDraftCanaryAdapterError('communications canary vertical mismatch')
        if provider_id != self.PROVIDER_ID:
            raise CommunicationsDraftCanaryAdapterError('communications canary provider mismatch')
        if action_key not in self.ALLOWED_ACTIONS:
            raise CommunicationsDraftCanaryAdapterError('communications canary action not allowed')
        if not scope.strip():
            raise CommunicationsDraftCanaryAdapterError('explicit canary scope required')
        if not isinstance(payload,dict):
            raise CommunicationsDraftCanaryAdapterError('payload must be a mapping')

        forbidden={'send','deliver','dispatch','provider_write','network','webhook','smtp','api_send'}
        if forbidden.intersection(payload):
            raise CommunicationsDraftCanaryAdapterError('outbound/provider transport fields forbidden')

        draft_id=str(payload.get('draft_id','')).strip()
        if not draft_id:
            raise CommunicationsDraftCanaryAdapterError('draft_id required')
        if action_key=='render-message-preview' and not str(payload.get('body','')).strip():
            raise CommunicationsDraftCanaryAdapterError('render-message-preview requires body')
        if action_key=='inspect-recipient-plan':
            recipients=payload.get('recipient_refs')
            if not isinstance(recipients,list) or not recipients:
                raise CommunicationsDraftCanaryAdapterError('inspect-recipient-plan requires recipient_refs')

        payload_hash=self._hash(payload)
        provider_ref='communications-preview-'+self._hash({
            'provider':provider_id,'action':action_key,'payload_hash':payload_hash,
            'idempotency_key':idempotency_key})[:24]
        preview={
            'draft_id':draft_id,
            'action_key':action_key,
            'recipient_count':len(payload.get('recipient_refs') or []),
            'outbound_send_performed':False,
            'provider_write_performed':False,
            'network_calls_made':0,
        }

        with self._connect() as conn:
            existing=conn.execute(
                'SELECT provider_ref FROM communications_draft_canary_actions WHERE idempotency_key=?',
                (idempotency_key,),).fetchone()
            if existing:
                return str(existing['provider_ref'])
            conn.execute('''INSERT INTO communications_draft_canary_actions
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',(
                provider_ref,vertical,provider_id,scope.strip(),action_key,
                json.dumps(payload,sort_keys=True,separators=(',',':')),payload_hash,idempotency_key,
                'completed',json.dumps(preview,sort_keys=True,separators=(',',':')),self._now()))
        return provider_ref

    def read_result(self, *, provider_ref: str) -> CanaryProviderResult:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM communications_draft_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None:
            raise CommunicationsDraftCanaryAdapterError('communications canary result not found')
        return CanaryProviderResult(
            str(row['provider_ref']),str(row['vertical']),str(row['provider_id']),str(row['state']),
            str(row['action_key']),str(row['payload_hash']),external_calls_made=0)

    def preview(self, provider_ref: str) -> dict:
        with self._connect() as conn:
            row=conn.execute('SELECT preview_json FROM communications_draft_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None:
            raise CommunicationsDraftCanaryAdapterError('communications preview not found')
        return json.loads(row['preview_json'])

    def stop_canary(self, *, activation_id: str, reason: str) -> None:
        if not activation_id.strip():
            raise CommunicationsDraftCanaryAdapterError('activation id required')
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_draft_canary_stops VALUES (?,?,?)
                ON CONFLICT(activation_id) DO UPDATE SET reason=excluded.reason,stopped_at=excluded.stopped_at''',
                (activation_id.strip(),reason.strip() or 'unspecified',self._now()))

    def is_stopped(self, activation_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute('SELECT 1 FROM communications_draft_canary_stops WHERE activation_id=?',(activation_id,)).fetchone() is not None
