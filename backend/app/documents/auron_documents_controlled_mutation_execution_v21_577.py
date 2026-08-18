from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.documents.auron_documents_mutation_simulation_v21_576 import DocumentsMutationSimulationService
from app.documents.auron_documents_provenance_access_policy_v21_575 import DocumentsProvenanceVersionAccessPolicy
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore


class DocumentsMutationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsMutationExecutionScope:
    provider_id: str
    enabled: bool
    operator_enabled: bool
    kill_switch: bool
    updated_at: str


@dataclass(frozen=True)
class DocumentsProviderMutationResult:
    provider_ref: str
    provider_item_ref: str | None
    provider_version_ref: str | None
    state: str
    external_calls_made: int = 1


@dataclass(frozen=True)
class DocumentsMutationExecutionDecision:
    execution_id: str
    plan_id: str
    provider_id: str
    actor_id: str
    kind: str
    state: str
    blockers: tuple[str, ...]
    idempotency_key: str
    provider_ref: str | None
    created_at: str
    external_calls_made: int


class DocumentsMutationWriter(Protocol):
    def execute_mutation(self, *, plan, idempotency_key: str) -> DocumentsProviderMutationResult: ...


class DisabledDocumentsMutationWriter:
    def execute_mutation(self, *, plan, idempotency_key: str) -> DocumentsProviderMutationResult:
        raise DocumentsMutationExecutionError('documents mutation writer is disabled')


class ControlledDocumentsMutationExecutionService:
    """D30 controlled execution boundary for D29 plans.

    Execution is disabled by default. A successful D29 plan is revalidated against current
    D28 provenance/version authorization and exact plan integrity immediately before the
    provider writer is called. Delete remains outside D30.
    """

    def __init__(self, db_path: str | Path, simulation: DocumentsMutationSimulationService,
                 registry: DocumentsRegistryStateStore,
                 policy: DocumentsProvenanceVersionAccessPolicy,
                 writer: DocumentsMutationWriter | None = None) -> None:
        self.db_path = str(db_path)
        self.simulation = simulation
        self.registry = registry
        self.policy = policy
        self.writer = writer or DisabledDocumentsMutationWriter()
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; return conn

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS document_mutation_execution_scopes (
                    provider_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                    operator_enabled INTEGER NOT NULL, kill_switch INTEGER NOT NULL,
                    updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS document_mutation_executions (
                    execution_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL UNIQUE,
                    provider_id TEXT NOT NULL, actor_id TEXT NOT NULL, kind TEXT NOT NULL,
                    state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, provider_ref TEXT,
                    created_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL);
            ''')

    def configure_scope(self, provider_id: str, *, enabled: bool, operator_enabled: bool,
                        kill_switch: bool = True, at: str | None = None) -> DocumentsMutationExecutionScope:
        provider = provider_id.strip()
        if not provider:
            raise DocumentsMutationExecutionError('provider id is required')
        scope = DocumentsMutationExecutionScope(provider, enabled, operator_enabled, kill_switch, at or self._now())
        with self._connect() as conn:
            conn.execute('''INSERT INTO document_mutation_execution_scopes VALUES (?,?,?,?,?)
                ON CONFLICT(provider_id) DO UPDATE SET enabled=excluded.enabled,
                operator_enabled=excluded.operator_enabled,kill_switch=excluded.kill_switch,
                updated_at=excluded.updated_at''',
                (provider, int(enabled), int(operator_enabled), int(kill_switch), scope.updated_at))
        return scope

    def get_scope(self, provider_id: str) -> DocumentsMutationExecutionScope | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM document_mutation_execution_scopes WHERE provider_id=?',(provider_id,)).fetchone()
        if not row: return None
        data=dict(row)
        for key in ('enabled','operator_enabled','kill_switch'): data[key]=bool(data[key])
        return DocumentsMutationExecutionScope(**data)

    def execute(self, plan_id: str) -> DocumentsMutationExecutionDecision:
        existing = self.get_by_plan(plan_id)
        if existing is not None:
            return existing
        plan = self.simulation.get_plan(plan_id)
        if plan is None:
            raise DocumentsMutationExecutionError('mutation plan not found')
        blockers: list[str] = []
        if plan.state != 'simulated-not-executed': blockers.append('successful-D29-plan-required')
        scope = self.get_scope(plan.provider_id)
        if scope is None or not scope.enabled: blockers.append('provider-execution-not-enabled')
        if scope is None or not scope.operator_enabled: blockers.append('operator-execution-not-enabled')
        if scope is None or scope.kill_switch: blockers.append('provider-kill-switch-active')

        if plan.kind in {'update','move'}:
            item = self.registry.get_item(plan.item_id) if plan.item_id else None
            if item is None: blockers.append('registered-item-required')
            else:
                if item.provider_id != plan.provider_id: blockers.append('provider-item-mismatch')
                if item.kind == 'file' and item.current_version_id != plan.expected_version_id:
                    blockers.append('current-version-drift')
                try:
                    self.policy.require_mutation_simulation_authorized(
                        item_id=item.item_id, version_id=plan.expected_version_id, actor_id=plan.actor_id)
                except Exception:
                    blockers.append('current-D28-authorization-required')
        elif plan.kind == 'create':
            parent = self.registry.get_item(plan.destination_parent_item_id) if plan.destination_parent_item_id else None
            if parent is None or parent.kind != 'folder' or parent.provider_id != plan.provider_id:
                blockers.append('valid-current-parent-required')
            elif not self.policy.evaluate(item_id=parent.item_id,actor_id=plan.actor_id,purpose='mutation-simulation').allowed:
                blockers.append('current-D28-parent-authorization-required')
        else:
            blockers.append('unsupported-mutation-kind')

        canonical = {
            'kind': plan.kind, 'provider_id': plan.provider_id, 'actor_id': plan.actor_id,
            'item_id': plan.item_id, 'expected_version_id': plan.expected_version_id,
            'source_parent_item_id': plan.source_parent_item_id,
            'destination_parent_item_id': plan.destination_parent_item_id,
            'name': plan.name, 'content_hash': plan.content_hash,
        }
        expected_hash = hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if expected_hash != plan.plan_hash: blockers.append('plan-integrity-mismatch')

        execution_id = 'docexec-' + hashlib.sha256(plan.plan_id.encode()).hexdigest()[:24]
        idempotency_key = execution_id
        provider_ref = None
        calls = 0
        if blockers:
            state = 'blocked'
        else:
            try:
                result = self.writer.execute_mutation(plan=plan,idempotency_key=idempotency_key)
                calls = result.external_calls_made
                provider_ref = result.provider_ref
                state = 'provider-submitted' if result.state in {'submitted','accepted'} else 'provider-result-unverified'
            except DocumentsMutationExecutionError:
                state = 'execution-transport-disabled'
            except Exception:
                state = 'execution-transport-error'; calls = 1

        decision = DocumentsMutationExecutionDecision(execution_id,plan.plan_id,plan.provider_id,
            plan.actor_id,plan.kind,state,tuple(dict.fromkeys(blockers)),idempotency_key,
            provider_ref,self._now(),calls)
        with self._connect() as conn:
            conn.execute('INSERT INTO document_mutation_executions VALUES (?,?,?,?,?,?,?,?,?,?,?)',(
                decision.execution_id,decision.plan_id,decision.provider_id,decision.actor_id,
                decision.kind,decision.state,json.dumps(decision.blockers),decision.idempotency_key,
                decision.provider_ref,decision.created_at,decision.external_calls_made))
        return decision

    def get_by_plan(self, plan_id: str) -> DocumentsMutationExecutionDecision | None:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM document_mutation_executions WHERE plan_id=?',(plan_id,)).fetchone()
        if not row: return None
        data=dict(row); data['blockers']=tuple(json.loads(data.pop('blockers_json')))
        return DocumentsMutationExecutionDecision(**data)
