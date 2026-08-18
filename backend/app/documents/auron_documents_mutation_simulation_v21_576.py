from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.documents.auron_documents_provenance_access_policy_v21_575 import DocumentsProvenanceVersionAccessPolicy
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore

MutationKind = Literal['create', 'update', 'move']


class DocumentsMutationSimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentMutationIntent:
    kind: MutationKind
    provider_id: str
    actor_id: str
    item_id: str | None = None
    expected_version_id: str | None = None
    parent_item_id: str | None = None
    destination_parent_item_id: str | None = None
    name: str | None = None
    content_hash: str | None = None


@dataclass(frozen=True)
class DocumentMutationPlan:
    plan_id: str
    kind: MutationKind
    provider_id: str
    actor_id: str
    item_id: str | None
    expected_version_id: str | None
    source_parent_item_id: str | None
    destination_parent_item_id: str | None
    name: str | None
    content_hash: str | None
    state: str
    plan_hash: str
    created_at: str
    external_calls_made: int = 0
    provider_writes_made: int = 0


class DocumentsMutationSimulationService:
    """D29 deterministic create/update/move dry-run. Never mutates provider storage."""

    def __init__(self, db_path: str | Path, registry: DocumentsRegistryStateStore,
                 policy: DocumentsProvenanceVersionAccessPolicy) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.policy = policy
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS document_mutation_plans (
                plan_id TEXT PRIMARY KEY, kind TEXT NOT NULL, provider_id TEXT NOT NULL,
                actor_id TEXT NOT NULL, item_id TEXT, expected_version_id TEXT,
                source_parent_item_id TEXT, destination_parent_item_id TEXT, name TEXT,
                content_hash TEXT, state TEXT NOT NULL, plan_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL,
                provider_writes_made INTEGER NOT NULL)''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def simulate(self, intent: DocumentMutationIntent, *, at: str | None = None) -> DocumentMutationPlan:
        provider, actor = intent.provider_id.strip(), intent.actor_id.strip()
        if intent.kind not in {'create','update','move'} or not provider or not actor:
            raise DocumentsMutationSimulationError('valid kind, provider and actor are required')

        source_parent = None
        if intent.kind == 'create':
            if intent.item_id or intent.expected_version_id:
                raise DocumentsMutationSimulationError('create cannot target an existing item/version')
            if not intent.parent_item_id or not intent.name or not intent.name.strip():
                raise DocumentsMutationSimulationError('create requires parent and name')
            parent = self.registry.get_item(intent.parent_item_id)
            if parent is None or parent.kind != 'folder' or parent.provider_id != provider:
                raise DocumentsMutationSimulationError('valid same-provider parent folder required')
            decision = self.policy.evaluate(item_id=parent.item_id, actor_id=actor, purpose='mutation-simulation')
            if not decision.allowed:
                raise DocumentsMutationSimulationError('create simulation is not authorized')
            destination = parent.item_id
        else:
            if not intent.item_id:
                raise DocumentsMutationSimulationError('existing item is required')
            item = self.registry.get_item(intent.item_id)
            if item is None or item.provider_id != provider:
                raise DocumentsMutationSimulationError('registered same-provider item required')
            source_parent = item.parent_item_id
            decision = self.policy.require_mutation_simulation_authorized(
                item_id=item.item_id, version_id=intent.expected_version_id, actor_id=actor)
            destination = source_parent
            if intent.kind == 'update':
                if item.kind != 'file' or not intent.content_hash:
                    raise DocumentsMutationSimulationError('update requires file and proposed content hash')
            if intent.kind == 'move':
                if not intent.destination_parent_item_id:
                    raise DocumentsMutationSimulationError('move requires destination parent')
                parent = self.registry.get_item(intent.destination_parent_item_id)
                if parent is None or parent.kind != 'folder' or parent.provider_id != provider:
                    raise DocumentsMutationSimulationError('valid same-provider destination folder required')
                parent_decision = self.policy.evaluate(item_id=parent.item_id, actor_id=actor, purpose='mutation-simulation')
                if not parent_decision.allowed:
                    raise DocumentsMutationSimulationError('destination parent is not authorized')
                destination = parent.item_id
                if destination == item.item_id:
                    raise DocumentsMutationSimulationError('item cannot be moved into itself')

        payload = {
            'kind': intent.kind, 'provider_id': provider, 'actor_id': actor,
            'item_id': intent.item_id, 'expected_version_id': intent.expected_version_id,
            'source_parent_item_id': source_parent, 'destination_parent_item_id': destination,
            'name': intent.name.strip() if intent.name else None, 'content_hash': intent.content_hash,
        }
        plan_hash = self._hash(payload)
        plan_id = 'docplan-' + plan_hash[:24]
        created = at or self._now()
        plan = DocumentMutationPlan(plan_id, intent.kind, provider, actor, intent.item_id,
                                    intent.expected_version_id, source_parent, destination,
                                    payload['name'], intent.content_hash, 'simulated-not-executed',
                                    plan_hash, created, 0, 0)
        with self._connect() as conn:
            existing = conn.execute('SELECT * FROM document_mutation_plans WHERE plan_id=?',(plan_id,)).fetchone()
            if existing:
                return DocumentMutationPlan(**dict(existing))
            conn.execute('INSERT INTO document_mutation_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         tuple(plan.__dict__.values()))
        return plan

    def get_plan(self, plan_id: str) -> DocumentMutationPlan | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM document_mutation_plans WHERE plan_id=?',(plan_id,)).fetchone()
        return DocumentMutationPlan(**dict(row)) if row else None
