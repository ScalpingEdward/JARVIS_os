from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.documents.auron_documents_controlled_mutation_execution_v21_577 import ControlledDocumentsMutationExecutionService
from app.documents.auron_documents_mutation_simulation_v21_576 import DocumentsMutationSimulationService
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore


class DocumentsReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsObservedMutationResult:
    provider_ref: str
    provider_id: str
    provider_item_ref: str | None
    provider_version_ref: str | None
    state: str
    content_hash: str | None = None
    parent_provider_item_ref: str | None = None
    external_calls_made: int = 1


@dataclass(frozen=True)
class DocumentsReconciliationRecord:
    execution_id: str
    plan_id: str
    state: str
    blockers: tuple[str, ...]
    attempt_count: int
    retry_eligible: bool
    conflict_detected: bool
    delete_authorized: bool
    reconciled_at: str
    external_calls_made: int


class DocumentsMutationResultReader(Protocol):
    def read_result(self, *, provider_ref: str) -> DocumentsObservedMutationResult: ...


class DisabledDocumentsMutationResultReader:
    def read_result(self, *, provider_ref: str) -> DocumentsObservedMutationResult:
        raise DocumentsReconciliationError('documents mutation result reader is disabled')


class DocumentsMutationReconciliationService:
    """D31 result reconciliation, conflict verification and bounded retry authorization.

    Delete is deliberately not implemented. D31 only exposes a permanent false delete
    authorization so no caller can infer delete permission from mutation success.
    """

    MAX_ATTEMPTS = 3

    def __init__(self, db_path: str | Path, execution: ControlledDocumentsMutationExecutionService,
                 simulation: DocumentsMutationSimulationService, registry: DocumentsRegistryStateStore,
                 reader: DocumentsMutationResultReader | None = None) -> None:
        self.db_path = str(db_path)
        self.execution = execution
        self.simulation = simulation
        self.registry = registry
        self.reader = reader or DisabledDocumentsMutationResultReader()
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS document_mutation_reconciliation (
                execution_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, state TEXT NOT NULL,
                blockers_json TEXT NOT NULL, attempt_count INTEGER NOT NULL,
                retry_eligible INTEGER NOT NULL, conflict_detected INTEGER NOT NULL,
                delete_authorized INTEGER NOT NULL, reconciled_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL)''')

    def reconcile(self, plan_id: str) -> DocumentsReconciliationRecord:
        decision=self.execution.get_by_plan(plan_id)
        if decision is None:
            raise DocumentsReconciliationError('execution decision not found')
        previous=self.get(decision.execution_id)
        attempts=(previous.attempt_count if previous else 0)+1
        blockers=[]; conflict=False; calls=0
        if decision.state != 'provider-submitted': blockers.append('provider-submitted-execution-required')
        if not decision.provider_ref: blockers.append('provider-result-reference-required')
        observed=None
        if not blockers:
            try:
                observed=self.reader.read_result(provider_ref=decision.provider_ref); calls=observed.external_calls_made
            except DocumentsReconciliationError:
                blockers.append('result-reader-disabled')
            except Exception:
                blockers.append('result-read-error'); calls=1
        plan=self.simulation.get_plan(plan_id)
        if plan is None: blockers.append('mutation-plan-not-found')
        if observed is not None and plan is not None:
            if observed.provider_ref != decision.provider_ref: blockers.append('provider-result-ref-mismatch')
            if observed.provider_id != decision.provider_id: blockers.append('provider-identity-mismatch')
            if observed.state not in {'completed','succeeded'}: blockers.append('provider-result-not-complete')
            if plan.kind == 'update':
                if observed.content_hash and plan.content_hash and observed.content_hash != plan.content_hash:
                    blockers.append('content-conflict'); conflict=True
                if not observed.provider_version_ref: blockers.append('result-version-missing')
            if plan.kind == 'move':
                destination=self.registry.get_item(plan.destination_parent_item_id) if plan.destination_parent_item_id else None
                if destination and observed.parent_provider_item_ref != destination.provider_item_ref:
                    blockers.append('parent-conflict'); conflict=True
            if plan.kind == 'create' and not observed.provider_item_ref:
                blockers.append('created-item-reference-missing')
        transient=set(blockers).issubset({'result-reader-disabled','result-read-error','provider-result-not-complete'})
        retry_eligible=bool(blockers) and transient and attempts < self.MAX_ATTEMPTS and not conflict
        if not blockers: state='reconciled'
        elif conflict: state='conflict'
        elif retry_eligible: state='retry-eligible'
        elif attempts >= self.MAX_ATTEMPTS: state='retry-exhausted'
        else: state='blocked'
        record=DocumentsReconciliationRecord(decision.execution_id,plan_id,state,tuple(dict.fromkeys(blockers)),
            attempts,retry_eligible,conflict,False,self._now(),calls)
        with self._connect() as conn:
            conn.execute('''INSERT INTO document_mutation_reconciliation VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(execution_id) DO UPDATE SET state=excluded.state,blockers_json=excluded.blockers_json,
                attempt_count=excluded.attempt_count,retry_eligible=excluded.retry_eligible,
                conflict_detected=excluded.conflict_detected,delete_authorized=0,
                reconciled_at=excluded.reconciled_at,external_calls_made=excluded.external_calls_made''',(
                record.execution_id,record.plan_id,record.state,json.dumps(record.blockers),record.attempt_count,
                int(record.retry_eligible),int(record.conflict_detected),0,record.reconciled_at,record.external_calls_made))
        return record

    def retry_authorization(self, execution_id: str) -> DocumentsReconciliationRecord:
        record=self.get(execution_id)
        if record is None or not record.retry_eligible:
            raise DocumentsReconciliationError('retry is not authorized')
        return record

    def authorize_delete(self, *args, **kwargs) -> bool:
        return False

    def get(self, execution_id: str) -> DocumentsReconciliationRecord | None:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM document_mutation_reconciliation WHERE execution_id=?',(execution_id,)).fetchone()
        if not row: return None
        data=dict(row); data['blockers']=tuple(json.loads(data.pop('blockers_json')))
        for key in ('retry_eligible','conflict_detected','delete_authorized'): data[key]=bool(data[key])
        return DocumentsReconciliationRecord(**data)
