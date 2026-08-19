from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryProviderResult


class DocumentsReadonlyCanaryAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsCanaryAdapterDescriptor:
    adapter_id: str
    vertical: str
    provider_id: str
    allowed_actions: tuple[str, ...]
    read_only: bool
    mutation_enabled: bool
    delete_enabled: bool
    move_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool


class DocumentsReadonlyCanaryAdapter:
    """G10 local read-only Files & Documents canary adapter.

    Implements the F2 execution and F3 result/stop boundaries against persistent local
    metadata/version-preview state. It never opens, mutates, moves or deletes provider files
    and never enables external network or production transport.
    """

    ADAPTER_ID='documents-readonly-canary-v1'
    VERTICAL='files-documents'
    PROVIDER_ID='documents-local-readonly'
    ALLOWED_ACTIONS=('inspect-file-metadata','preview-file-version')

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path); self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS documents_canary_actions(
                    provider_ref TEXT PRIMARY KEY,activation_id TEXT,vertical TEXT NOT NULL,
                    provider_id TEXT NOT NULL,scope TEXT NOT NULL,action_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,payload_hash TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,preview_json TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents_canary_stops(
                    activation_id TEXT PRIMARY KEY,reason TEXT NOT NULL,stopped_at TEXT NOT NULL);
            ''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def descriptor(self) -> DocumentsCanaryAdapterDescriptor:
        return DocumentsCanaryAdapterDescriptor(self.ADAPTER_ID,self.VERTICAL,self.PROVIDER_ID,self.ALLOWED_ACTIONS,
            True,False,False,False,False,False)

    def execute_canary_action(self, *, vertical: str, provider_id: str, scope: str,
                              action_key: str, payload: dict, idempotency_key: str) -> str:
        if vertical != self.VERTICAL: raise DocumentsReadonlyCanaryAdapterError('documents adapter vertical mismatch')
        if provider_id != self.PROVIDER_ID: raise DocumentsReadonlyCanaryAdapterError('documents adapter provider mismatch')
        if action_key not in self.ALLOWED_ACTIONS: raise DocumentsReadonlyCanaryAdapterError('documents canary action not allowed')
        if not scope.strip(): raise DocumentsReadonlyCanaryAdapterError('explicit canary scope required')
        if not isinstance(payload,dict): raise DocumentsReadonlyCanaryAdapterError('payload must be a mapping')
        file_id=str(payload.get('file_id','')).strip()
        if not file_id: raise DocumentsReadonlyCanaryAdapterError('file_id required')
        if action_key=='preview-file-version' and not str(payload.get('version_id','')).strip():
            raise DocumentsReadonlyCanaryAdapterError('preview-file-version requires version_id')
        forbidden={'content','bytes','write','delete','move','rename','destination','replacement'}
        if forbidden.intersection(payload): raise DocumentsReadonlyCanaryAdapterError('mutation/content payload fields forbidden')

        payload_hash=self._hash(payload)
        provider_ref='documents-canary-'+self._hash({'provider':provider_id,'action':action_key,'payload':payload_hash,'key':idempotency_key})[:24]
        preview={'file_id':file_id,'action':action_key,'version_id':str(payload.get('version_id','')).strip() or None,
                 'metadata_only':True,'content_read':False,'mutation_performed':False,'external_calls_made':0}
        with self._connect() as c:
            existing=c.execute('SELECT provider_ref FROM documents_canary_actions WHERE idempotency_key=?',(idempotency_key,)).fetchone()
            if existing: return str(existing['provider_ref'])
            c.execute('INSERT INTO documents_canary_actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (provider_ref,None,vertical,provider_id,scope.strip(),action_key,json.dumps(payload,sort_keys=True,separators=(',',':')),
                 payload_hash,idempotency_key,'completed',json.dumps(preview,sort_keys=True,separators=(',',':')),self._now()))
        return provider_ref

    def read_result(self, *, provider_ref: str) -> CanaryProviderResult:
        with self._connect() as c:
            row=c.execute('SELECT * FROM documents_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None: raise DocumentsReadonlyCanaryAdapterError('documents canary result not found')
        return CanaryProviderResult(str(row['provider_ref']),str(row['vertical']),str(row['provider_id']),str(row['state']),
            str(row['action_key']),str(row['payload_hash']),external_calls_made=0)

    def preview(self, provider_ref: str) -> dict:
        with self._connect() as c:
            row=c.execute('SELECT preview_json FROM documents_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None: raise DocumentsReadonlyCanaryAdapterError('documents preview not found')
        return json.loads(row['preview_json'])

    def stop_canary(self, *, activation_id: str, reason: str) -> None:
        if not activation_id.strip(): raise DocumentsReadonlyCanaryAdapterError('activation id required')
        with self._connect() as c:
            c.execute('''INSERT INTO documents_canary_stops VALUES (?,?,?) ON CONFLICT(activation_id)
                DO UPDATE SET reason=excluded.reason,stopped_at=excluded.stopped_at''',
                (activation_id.strip(),reason.strip() or 'unspecified',self._now()))

    def is_stopped(self, activation_id: str) -> bool:
        with self._connect() as c:
            return c.execute('SELECT 1 FROM documents_canary_stops WHERE activation_id=?',(activation_id,)).fetchone() is not None
