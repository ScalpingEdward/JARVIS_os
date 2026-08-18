from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryProviderResult


class ResearchReadonlyCanaryAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchCanaryAdapterDescriptor:
    adapter_id: str
    vertical: str
    provider_id: str
    allowed_actions: tuple[str, ...]
    read_only: bool
    network_transport_enabled: bool
    production_transport_enabled: bool


class ResearchReadonlyCanaryAdapter:
    """G1 provider-specific canary adapter for the Research vertical.

    This is deliberately the first canary adapter because it is read-only and side-effect free.
    It implements the F2 execution, F3 result-reader and F3 stop boundaries against a local
    persistent adapter state. No external network or production provider transport is enabled.
    """

    ADAPTER_ID = 'research-readonly-canary-v1'
    VERTICAL = 'research'
    PROVIDER_ID = 'research-local-readonly'
    ALLOWED_ACTIONS = ('search-preview', 'inspect-source-metadata')

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS research_canary_actions (
                    provider_ref TEXT PRIMARY KEY,
                    activation_id TEXT,
                    vertical TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_canary_stops (
                    activation_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    stopped_at TEXT NOT NULL
                );
            ''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def descriptor(self) -> ResearchCanaryAdapterDescriptor:
        return ResearchCanaryAdapterDescriptor(
            adapter_id=self.ADAPTER_ID,
            vertical=self.VERTICAL,
            provider_id=self.PROVIDER_ID,
            allowed_actions=self.ALLOWED_ACTIONS,
            read_only=True,
            network_transport_enabled=False,
            production_transport_enabled=False,
        )

    def execute_canary_action(self, *, vertical: str, provider_id: str, scope: str,
                              action_key: str, payload: dict, idempotency_key: str) -> str:
        if vertical != self.VERTICAL:
            raise ResearchReadonlyCanaryAdapterError('research adapter vertical mismatch')
        if provider_id != self.PROVIDER_ID:
            raise ResearchReadonlyCanaryAdapterError('research adapter provider mismatch')
        if action_key not in self.ALLOWED_ACTIONS:
            raise ResearchReadonlyCanaryAdapterError('research canary action not allowed')
        if not scope.strip():
            raise ResearchReadonlyCanaryAdapterError('explicit canary scope required')
        if not isinstance(payload, dict):
            raise ResearchReadonlyCanaryAdapterError('payload must be a mapping')
        if action_key == 'search-preview' and not str(payload.get('query', '')).strip():
            raise ResearchReadonlyCanaryAdapterError('search-preview requires query')
        if action_key == 'inspect-source-metadata' and not str(payload.get('source_id', '')).strip():
            raise ResearchReadonlyCanaryAdapterError('inspect-source-metadata requires source_id')

        payload_hash = self._hash(payload)
        provider_ref = 'research-canary-' + self._hash({
            'provider_id': provider_id,
            'action_key': action_key,
            'payload_hash': payload_hash,
            'idempotency_key': idempotency_key,
        })[:24]

        with self._connect() as conn:
            existing = conn.execute(
                'SELECT provider_ref FROM research_canary_actions WHERE idempotency_key=?',
                (idempotency_key,),
            ).fetchone()
            if existing:
                return str(existing['provider_ref'])
            conn.execute(
                '''INSERT INTO research_canary_actions(
                    provider_ref,activation_id,vertical,provider_id,scope,action_key,
                    payload_json,payload_hash,idempotency_key,state,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (provider_ref, None, vertical, provider_id, scope.strip(), action_key,
                 json.dumps(payload, sort_keys=True, separators=(',', ':')), payload_hash,
                 idempotency_key, 'completed', self._now()),
            )
        return provider_ref

    def read_result(self, *, provider_ref: str) -> CanaryProviderResult:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM research_canary_actions WHERE provider_ref=?',
                (provider_ref,),
            ).fetchone()
        if row is None:
            raise ResearchReadonlyCanaryAdapterError('research canary result not found')
        return CanaryProviderResult(
            provider_ref=str(row['provider_ref']),
            vertical=str(row['vertical']),
            provider_id=str(row['provider_id']),
            state=str(row['state']),
            action_key=str(row['action_key']),
            payload_hash=str(row['payload_hash']),
            external_calls_made=0,
        )

    def stop_canary(self, *, activation_id: str, reason: str) -> None:
        if not activation_id.strip():
            raise ResearchReadonlyCanaryAdapterError('activation id required')
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO research_canary_stops(activation_id,reason,stopped_at)
                   VALUES (?,?,?)
                   ON CONFLICT(activation_id) DO UPDATE SET reason=excluded.reason,stopped_at=excluded.stopped_at''',
                (activation_id.strip(), reason.strip() or 'unspecified', self._now()),
            )

    def is_stopped(self, activation_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT 1 FROM research_canary_stops WHERE activation_id=?',
                (activation_id,),
            ).fetchone()
        return row is not None
