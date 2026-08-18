from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

DocumentKind = Literal['file', 'folder']
DocumentState = Literal['active', 'trashed', 'missing']


class DocumentsRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentItem:
    item_id: str
    provider_id: str
    provider_item_ref: str
    kind: DocumentKind
    name: str
    parent_item_id: str | None
    mime_type: str | None
    state: DocumentState
    current_version_id: str | None
    metadata_json: str
    observed_at: str
    integrity_hash: str


@dataclass(frozen=True)
class DocumentVersion:
    version_id: str
    item_id: str
    provider_version_ref: str
    content_hash: str | None
    size_bytes: int | None
    modified_at: str | None
    observed_at: str
    metadata_json: str
    integrity_hash: str


class DocumentsRegistryStateStore:
    """D26 provider-neutral persistent file/folder/version state.

    This layer stores normalized observations only. It has no provider mutation transport,
    create/update/move/delete method or cross-vertical execution path.
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

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        raw = '\x1f'.join(parts).encode('utf-8')
        return f'{prefix}-' + hashlib.sha256(raw).hexdigest()[:24]

    @staticmethod
    def _canonical_json(value: dict | None) -> str:
        return json.dumps(value or {}, sort_keys=True, separators=(',', ':'))

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS document_items (
                    item_id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    provider_item_ref TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_item_id TEXT,
                    mime_type TEXT,
                    state TEXT NOT NULL,
                    current_version_id TEXT,
                    metadata_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    UNIQUE(provider_id, provider_item_ref),
                    FOREIGN KEY(parent_item_id) REFERENCES document_items(item_id));
                CREATE TABLE IF NOT EXISTS document_versions (
                    version_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    provider_version_ref TEXT NOT NULL,
                    content_hash TEXT,
                    size_bytes INTEGER,
                    modified_at TEXT,
                    observed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    UNIQUE(item_id, provider_version_ref),
                    FOREIGN KEY(item_id) REFERENCES document_items(item_id));
                CREATE INDEX IF NOT EXISTS idx_document_items_parent
                    ON document_items(parent_item_id, name);
                CREATE INDEX IF NOT EXISTS idx_document_versions_item
                    ON document_versions(item_id, observed_at);
            ''')

    def observe_item(self, *, provider_id: str, provider_item_ref: str,
                     kind: DocumentKind, name: str, parent_item_id: str | None = None,
                     mime_type: str | None = None, state: DocumentState = 'active',
                     metadata: dict | None = None, observed_at: str | None = None) -> DocumentItem:
        provider = provider_id.strip()
        provider_ref = provider_item_ref.strip()
        clean_name = name.strip()
        if not provider or not provider_ref or not clean_name:
            raise DocumentsRegistryError('provider, provider item ref and name are required')
        if kind not in {'file', 'folder'}:
            raise DocumentsRegistryError('unsupported document kind')
        if state not in {'active', 'trashed', 'missing'}:
            raise DocumentsRegistryError('unsupported document state')
        if parent_item_id:
            parent = self.get_item(parent_item_id)
            if parent is None:
                raise DocumentsRegistryError('parent item not found')
            if parent.provider_id != provider:
                raise DocumentsRegistryError('cross-provider parent is not allowed')
            if parent.kind != 'folder':
                raise DocumentsRegistryError('parent item must be a folder')
        at = observed_at or self._now()
        item_id = self._stable_id('doc', provider, provider_ref)
        metadata_json = self._canonical_json(metadata)
        existing = self.get_item(item_id)
        current_version_id = existing.current_version_id if existing else None
        payload = {
            'item_id': item_id, 'provider_id': provider, 'provider_item_ref': provider_ref,
            'kind': kind, 'name': clean_name, 'parent_item_id': parent_item_id,
            'mime_type': mime_type, 'state': state,
            'current_version_id': current_version_id, 'metadata_json': metadata_json,
        }
        item = DocumentItem(item_id, provider, provider_ref, kind, clean_name,
                            parent_item_id, mime_type, state, current_version_id,
                            metadata_json, at, self._hash(payload))
        with self._connect() as conn:
            conn.execute('''INSERT INTO document_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(item_id) DO UPDATE SET kind=excluded.kind,name=excluded.name,
                parent_item_id=excluded.parent_item_id,mime_type=excluded.mime_type,
                state=excluded.state,metadata_json=excluded.metadata_json,
                observed_at=excluded.observed_at,integrity_hash=excluded.integrity_hash''',
                tuple(item.__dict__.values()))
        return self.get_item(item_id) or item

    def observe_version(self, *, item_id: str, provider_version_ref: str,
                        content_hash: str | None = None, size_bytes: int | None = None,
                        modified_at: str | None = None, metadata: dict | None = None,
                        observed_at: str | None = None, make_current: bool = True) -> DocumentVersion:
        item = self.get_item(item_id)
        if item is None:
            raise DocumentsRegistryError('item not found')
        if item.kind != 'file':
            raise DocumentsRegistryError('folders cannot have file versions')
        provider_ref = provider_version_ref.strip()
        if not provider_ref:
            raise DocumentsRegistryError('provider version ref is required')
        if size_bytes is not None and size_bytes < 0:
            raise DocumentsRegistryError('size_bytes must be >= 0')
        at = observed_at or self._now()
        metadata_json = self._canonical_json(metadata)
        version_id = self._stable_id('ver', item_id, provider_ref)
        payload = {
            'version_id': version_id, 'item_id': item_id,
            'provider_version_ref': provider_ref, 'content_hash': content_hash,
            'size_bytes': size_bytes, 'modified_at': modified_at,
            'metadata_json': metadata_json,
        }
        version = DocumentVersion(version_id, item_id, provider_ref, content_hash,
                                  size_bytes, modified_at, at, metadata_json,
                                  self._hash(payload))
        with self._connect() as conn:
            existing = conn.execute('SELECT integrity_hash FROM document_versions WHERE version_id=?',
                                    (version_id,)).fetchone()
            if existing and existing['integrity_hash'] != version.integrity_hash:
                raise DocumentsRegistryError('version identity reused with different immutable payload')
            conn.execute('''INSERT OR IGNORE INTO document_versions VALUES (?,?,?,?,?,?,?,?,?)''',
                         tuple(version.__dict__.values()))
            if make_current:
                conn.execute('UPDATE document_items SET current_version_id=?,observed_at=? WHERE item_id=?',
                             (version_id, at, item_id))
        return self.get_version(version_id) or version

    def get_item(self, item_id: str) -> DocumentItem | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM document_items WHERE item_id=?', (item_id,)).fetchone()
        return DocumentItem(**dict(row)) if row else None

    def get_item_by_provider_ref(self, provider_id: str, provider_item_ref: str) -> DocumentItem | None:
        with self._connect() as conn:
            row = conn.execute('''SELECT * FROM document_items
                                  WHERE provider_id=? AND provider_item_ref=?''',
                               (provider_id, provider_item_ref)).fetchone()
        return DocumentItem(**dict(row)) if row else None

    def get_version(self, version_id: str) -> DocumentVersion | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM document_versions WHERE version_id=?', (version_id,)).fetchone()
        return DocumentVersion(**dict(row)) if row else None

    def list_children(self, parent_item_id: str | None, *, provider_id: str | None = None) -> tuple[DocumentItem, ...]:
        with self._connect() as conn:
            if parent_item_id is None:
                if provider_id is None:
                    rows = conn.execute('SELECT * FROM document_items WHERE parent_item_id IS NULL ORDER BY name,item_id').fetchall()
                else:
                    rows = conn.execute('''SELECT * FROM document_items WHERE parent_item_id IS NULL
                                           AND provider_id=? ORDER BY name,item_id''', (provider_id,)).fetchall()
            else:
                rows = conn.execute('SELECT * FROM document_items WHERE parent_item_id=? ORDER BY name,item_id',
                                    (parent_item_id,)).fetchall()
        return tuple(DocumentItem(**dict(row)) for row in rows)

    def list_versions(self, item_id: str) -> tuple[DocumentVersion, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT * FROM document_versions WHERE item_id=?
                                   ORDER BY observed_at,version_id''', (item_id,)).fetchall()
        return tuple(DocumentVersion(**dict(row)) for row in rows)

    def snapshot(self, provider_id: str | None = None) -> dict:
        with self._connect() as conn:
            if provider_id is None:
                items = conn.execute('SELECT * FROM document_items ORDER BY provider_id,name,item_id').fetchall()
            else:
                items = conn.execute('SELECT * FROM document_items WHERE provider_id=? ORDER BY name,item_id',
                                     (provider_id,)).fetchall()
        normalized_items = tuple(DocumentItem(**dict(row)) for row in items)
        return {
            'items': normalized_items,
            'versions': tuple(v for item in normalized_items for v in self.list_versions(item.item_id)),
            'write_enabled': False,
            'delete_enabled': False,
            'external_calls_made': 0,
        }
