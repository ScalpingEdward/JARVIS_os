from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore

AccessPurpose = Literal['read', 'mutation-simulation', 'mutation-execution']


class DocumentsPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsAccessGrant:
    grant_id: str
    actor_id: str
    provider_id: str
    item_id: str | None
    allowed_purposes: tuple[str, ...]
    state: str
    granted_at: str
    revoked_at: str | None


@dataclass(frozen=True)
class DocumentsPolicyDecision:
    item_id: str
    version_id: str | None
    actor_id: str
    purpose: AccessPurpose
    allowed: bool
    blockers: tuple[str, ...]
    provenance_verified: bool
    version_verified: bool
    access_verified: bool
    current_version_required: bool
    external_calls_made: int = 0


class DocumentsProvenanceVersionAccessPolicy:
    """D28 fail-closed provenance/version/access authorization policy.

    Read access requires a registered provider-scoped item and explicit grant. Future
    mutation simulation additionally requires a file's exact current version identity.
    Mutation execution is deliberately not authorized in D28.
    """

    def __init__(self, db_path: str | Path, registry: DocumentsRegistryStateStore) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _grant_id(actor_id: str, provider_id: str, item_id: str | None) -> str:
        raw = f'{actor_id}\x1f{provider_id}\x1f{item_id or "*"}'.encode()
        return 'docgrant-' + hashlib.sha256(raw).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS document_access_grants (
                grant_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, provider_id TEXT NOT NULL,
                item_id TEXT, allowed_purposes TEXT NOT NULL, state TEXT NOT NULL,
                granted_at TEXT NOT NULL, revoked_at TEXT)''')

    def grant(self, *, actor_id: str, provider_id: str, item_id: str | None = None,
              allowed_purposes: tuple[str, ...] = ('read',), at: str | None = None) -> DocumentsAccessGrant:
        actor, provider = actor_id.strip(), provider_id.strip()
        purposes = tuple(sorted(set(p.strip() for p in allowed_purposes if p.strip())))
        valid = {'read', 'mutation-simulation'}
        if not actor or not provider or not purposes:
            raise DocumentsPolicyError('actor, provider and access purpose are required')
        if any(p not in valid for p in purposes):
            raise DocumentsPolicyError('D28 cannot grant mutation execution')
        if item_id:
            item = self.registry.get_item(item_id)
            if item is None:
                raise DocumentsPolicyError('item not found')
            if item.provider_id != provider:
                raise DocumentsPolicyError('grant provider/item mismatch')
        now = at or self._now()
        grant = DocumentsAccessGrant(self._grant_id(actor, provider, item_id), actor, provider,
                                     item_id, purposes, 'active', now, None)
        with self._connect() as conn:
            conn.execute('''INSERT INTO document_access_grants VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(grant_id) DO UPDATE SET allowed_purposes=excluded.allowed_purposes,
                state='active',granted_at=excluded.granted_at,revoked_at=NULL''',
                (grant.grant_id, grant.actor_id, grant.provider_id, grant.item_id,
                 ','.join(grant.allowed_purposes), grant.state, grant.granted_at, grant.revoked_at))
        return grant

    def revoke(self, grant_id: str, *, at: str | None = None) -> DocumentsAccessGrant:
        grant = self.get_grant(grant_id)
        if grant is None:
            raise DocumentsPolicyError('grant not found')
        now = at or self._now()
        with self._connect() as conn:
            conn.execute('UPDATE document_access_grants SET state=?,revoked_at=? WHERE grant_id=?',
                         ('revoked', now, grant_id))
        return self.get_grant(grant_id)

    def evaluate(self, *, item_id: str, actor_id: str, purpose: AccessPurpose = 'read',
                 version_id: str | None = None) -> DocumentsPolicyDecision:
        blockers: list[str] = []
        item = self.registry.get_item(item_id)
        provenance = item is not None and bool(item.provider_id and item.provider_item_ref)
        if not provenance:
            blockers.append('registered-provenance-required')

        current_required = purpose == 'mutation-simulation'
        version_verified = True
        if item and item.kind == 'file' and current_required:
            if not item.current_version_id:
                version_verified = False
                blockers.append('current-version-required')
            elif version_id != item.current_version_id:
                version_verified = False
                blockers.append('exact-current-version-required')
            elif self.registry.get_version(version_id) is None:
                version_verified = False
                blockers.append('registered-version-required')
        elif item and item.kind == 'folder' and version_id is not None:
            version_verified = False
            blockers.append('folder-version-not-allowed')

        if purpose == 'mutation-execution':
            blockers.append('D28-mutation-execution-not-authorized')

        access = False
        if item is not None:
            access = self._has_access(actor_id.strip(), item.provider_id, item.item_id, purpose)
        if not access:
            blockers.append('explicit-access-grant-required')

        return DocumentsPolicyDecision(
            item_id=item_id, version_id=version_id, actor_id=actor_id.strip(), purpose=purpose,
            allowed=not blockers, blockers=tuple(dict.fromkeys(blockers)),
            provenance_verified=provenance, version_verified=version_verified,
            access_verified=access, current_version_required=current_required, external_calls_made=0,
        )

    def require_mutation_simulation_authorized(self, *, item_id: str, version_id: str | None,
                                               actor_id: str) -> DocumentsPolicyDecision:
        decision = self.evaluate(item_id=item_id, version_id=version_id, actor_id=actor_id,
                                 purpose='mutation-simulation')
        if not decision.allowed:
            raise DocumentsPolicyError('document mutation simulation is not authorized')
        return decision

    def _has_access(self, actor_id: str, provider_id: str, item_id: str, purpose: str) -> bool:
        with self._connect() as conn:
            rows = conn.execute('''SELECT allowed_purposes,item_id,state FROM document_access_grants
                WHERE actor_id=? AND provider_id=? AND state='active' AND (item_id=? OR item_id IS NULL)''',
                (actor_id, provider_id, item_id)).fetchall()
        return any(purpose in set(filter(None, row['allowed_purposes'].split(','))) for row in rows)

    def get_grant(self, grant_id: str) -> DocumentsAccessGrant | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM document_access_grants WHERE grant_id=?', (grant_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['allowed_purposes'] = tuple(filter(None, data['allowed_purposes'].split(',')))
        return DocumentsAccessGrant(**data)
