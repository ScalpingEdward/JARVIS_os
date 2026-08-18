from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.documents.auron_documents_controlled_mutation_execution_v21_577 import ControlledDocumentsMutationExecutionService
from app.documents.auron_documents_mutation_simulation_v21_576 import DocumentsMutationSimulationService
from app.documents.auron_documents_provenance_access_policy_v21_575 import DocumentsProvenanceVersionAccessPolicy
from app.documents.auron_documents_reconciliation_conflicts_v21_578 import DocumentsMutationReconciliationService
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore


class DocumentsCommandCentreError(RuntimeError): pass


@dataclass(frozen=True)
class DocumentsCommandJournalEntry:
    command_id: int
    actor: str
    command_text: str
    state: str
    created_at: str


class DocumentsCommandCentre:
    """D32 operational read model and governed controls for Files & Documents."""

    def __init__(self, db_path: str | Path, registry: DocumentsRegistryStateStore,
                 policy: DocumentsProvenanceVersionAccessPolicy,
                 simulation: DocumentsMutationSimulationService,
                 execution: ControlledDocumentsMutationExecutionService,
                 reconciliation: DocumentsMutationReconciliationService) -> None:
        self.db_path=str(db_path); self.registry=registry; self.policy=policy
        self.simulation=simulation; self.execution=execution; self.reconciliation=reconciliation
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS document_command_journal (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,
                command_text TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL)''')

    @staticmethod
    def _rows(db_path: str, sql: str) -> tuple[dict,...]:
        conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
        try: return tuple(dict(r) for r in conn.execute(sql).fetchall())
        except sqlite3.OperationalError: return ()
        finally: conn.close()

    @staticmethod
    def _record_dict(record) -> dict:
        if is_dataclass(record): return asdict(record)
        try: return dict(vars(record))
        except (TypeError,AttributeError) as exc: raise DocumentsCommandCentreError('control result is not serializable') from exc

    def snapshot(self) -> dict:
        items=self._rows(self.registry.db_path,'SELECT * FROM document_items ORDER BY observed_at DESC,item_id')
        versions=self._rows(self.registry.db_path,'SELECT * FROM document_versions ORDER BY observed_at DESC,version_id')
        grants=self._rows(self.policy.db_path,'SELECT * FROM document_access_grants ORDER BY granted_at DESC,grant_id')
        plans=self._rows(self.simulation.db_path,'SELECT * FROM document_mutation_plans ORDER BY created_at DESC,plan_id')
        scopes=self._rows(self.execution.db_path,'SELECT * FROM document_mutation_execution_scopes ORDER BY provider_id')
        executions=self._rows(self.execution.db_path,'SELECT * FROM document_mutation_executions ORDER BY created_at DESC,execution_id')
        reconciliations=self._rows(self.reconciliation.db_path,'SELECT * FROM document_mutation_reconciliation ORDER BY reconciled_at DESC,execution_id')
        alerts=[]
        for s in scopes:
            if s['kill_switch']: alerts.append({'kind':'kill-switch','severity':'info','provider_id':s['provider_id'],'state':'active'})
        for e in executions:
            if e['state'] in {'blocked','execution-transport-disabled','execution-transport-error','provider-result-unverified'}:
                alerts.append({'kind':'execution','severity':'warning','execution_id':e['execution_id'],'state':e['state']})
        for r in reconciliations:
            if r['state'] in {'conflict','retry-eligible','retry-exhausted','blocked'}:
                alerts.append({'kind':'reconciliation','severity':'warning','execution_id':r['execution_id'],'state':r['state']})
        return {'workspace':'files-documents','command_field_enabled':True,'items':items,'versions':versions,
            'access_grants':grants,'mutation_plans':plans,'execution_scopes':scopes,'executions':executions,
            'reconciliations':reconciliations,'alerts':tuple(alerts),'provider_mutations_enabled_by_default':False,
            'delete_enabled':False,'recorded_commands_execute_directly':False}

    def set_execution_kill_switch(self, provider_id: str, *, active: bool) -> dict:
        scope=self.execution.get_scope(provider_id)
        if scope is None: raise DocumentsCommandCentreError('execution scope not configured')
        updated=self.execution.configure_scope(provider_id,enabled=scope.enabled,operator_enabled=scope.operator_enabled,kill_switch=active)
        return self._record_dict(updated)

    def retry_status(self, execution_id: str) -> dict:
        try: return self._record_dict(self.reconciliation.retry_authorization(execution_id))
        except Exception as exc: raise DocumentsCommandCentreError('retry is not authorized') from exc

    def delete_authorized(self, *args, **kwargs) -> bool:
        return False

    def record_command(self, command_text: str, *, actor: str) -> DocumentsCommandJournalEntry:
        command,operator=command_text.strip(),actor.strip()
        if not command or not operator: raise DocumentsCommandCentreError('command text and actor are required')
        with self._connect() as conn:
            cur=conn.execute('INSERT INTO document_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (operator,command,'recorded-not-executed',self._now())); command_id=int(cur.lastrowid)
        return self.get_command(command_id)

    def get_command(self, command_id: int) -> DocumentsCommandJournalEntry:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM document_command_journal WHERE command_id=?',(command_id,)).fetchone()
        if row is None: raise DocumentsCommandCentreError('command not found')
        return DocumentsCommandJournalEntry(**dict(row))
