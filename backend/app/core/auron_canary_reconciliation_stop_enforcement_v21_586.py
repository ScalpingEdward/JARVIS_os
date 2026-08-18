from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.core.auron_controlled_canary_execution_boundary_v21_585 import (
    CanaryExecutionRecord,
    ControlledCanaryExecutionService,
)


class CanaryReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanaryProviderResult:
    provider_ref: str
    vertical: str
    provider_id: str
    state: str
    action_key: str
    payload_hash: str
    external_calls_made: int = 1


@dataclass(frozen=True)
class CanaryReconciliationRecord:
    reconciliation_id: str
    execution_id: str
    activation_id: str
    state: str
    blockers: tuple[str, ...]
    stop_required: bool
    stop_enforced: bool
    progression_authorized: bool
    external_calls_made: int
    reconciled_at: str


class CanaryResultReader(Protocol):
    def read_result(self, *, provider_ref: str) -> CanaryProviderResult: ...


class CanaryStopBoundary(Protocol):
    def stop_canary(self, *, activation_id: str, reason: str) -> None: ...


class DisabledCanaryResultReader:
    def read_result(self, *, provider_ref: str) -> CanaryProviderResult:
        raise CanaryReconciliationError('canary result reader is disabled')


class DisabledCanaryStopBoundary:
    def stop_canary(self, *, activation_id: str, reason: str) -> None:
        raise CanaryReconciliationError('canary stop boundary is disabled')


class CanaryReconciliationStopService:
    """F3: every submitted canary action must reconcile before progression.

    Any mismatch, missing/failing result, or safety drift requires an immediate stop. A stop
    failure remains fail-closed and progression is never authorized.
    """

    def __init__(self, db_path: str | Path, executions: ControlledCanaryExecutionService,
                 reader: CanaryResultReader | None = None,
                 stopper: CanaryStopBoundary | None = None) -> None:
        self.db_path = str(db_path)
        self.executions = executions
        self.reader = reader or DisabledCanaryResultReader()
        self.stopper = stopper or DisabledCanaryStopBoundary()
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS canary_reconciliations (
                reconciliation_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL UNIQUE,
                activation_id TEXT NOT NULL, state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                stop_required INTEGER NOT NULL, stop_enforced INTEGER NOT NULL,
                progression_authorized INTEGER NOT NULL, external_calls_made INTEGER NOT NULL,
                reconciled_at TEXT NOT NULL)''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    def reconcile(self, execution: CanaryExecutionRecord, *, kill_switch_active: bool,
                  reconciliation_ready: bool, stop_control_ready: bool) -> CanaryReconciliationRecord:
        existing=self.get_by_execution(execution.execution_id)
        if existing: return existing
        blockers=[]; calls=0; observed=None
        if execution.state != 'provider-submitted': blockers.append('provider-submitted-execution-required')
        if not execution.provider_ref: blockers.append('provider-reference-required')
        if not kill_switch_active: blockers.append('kill-switch-drift')
        if not reconciliation_ready: blockers.append('reconciliation-safety-drift')
        if not stop_control_ready: blockers.append('stop-control-safety-drift')
        if not blockers:
            try:
                observed=self.reader.read_result(provider_ref=execution.provider_ref)
                calls=max(1, observed.external_calls_made)
            except Exception:
                calls=1; blockers.append('provider-result-missing-or-read-failed')
        if observed is not None:
            if observed.provider_ref != execution.provider_ref: blockers.append('provider-result-ref-mismatch')
            if observed.vertical != execution.vertical: blockers.append('vertical-mismatch')
            if observed.provider_id != execution.provider_id: blockers.append('provider-identity-mismatch')
            if observed.action_key != execution.action_key: blockers.append('action-key-mismatch')
            if observed.payload_hash != execution.payload_hash: blockers.append('payload-hash-mismatch')
            if observed.state not in {'succeeded','completed'}: blockers.append('provider-result-failed')
        stop_required=bool(blockers); stop_enforced=False
        if stop_required:
            try:
                self.stopper.stop_canary(activation_id=execution.activation_id, reason=';'.join(dict.fromkeys(blockers)))
                calls += 1; stop_enforced=True
            except Exception:
                calls += 1; blockers.append('stop-enforcement-failed')
        state='reconciled' if not blockers else ('stopped' if stop_enforced else 'stop-failed')
        progression=state=='reconciled'
        rid='canary-rec-'+execution.execution_id.removeprefix('canary-exec-')
        record=CanaryReconciliationRecord(rid,execution.execution_id,execution.activation_id,state,
            tuple(dict.fromkeys(blockers)),stop_required,stop_enforced,progression,calls,self._now())
        with self._connect() as conn:
            conn.execute('INSERT INTO canary_reconciliations VALUES (?,?,?,?,?,?,?,?,?,?)',(
                record.reconciliation_id,record.execution_id,record.activation_id,record.state,
                json.dumps(record.blockers),int(record.stop_required),int(record.stop_enforced),
                int(record.progression_authorized),record.external_calls_made,record.reconciled_at))
        return record

    def require_progression(self, execution_id: str) -> CanaryReconciliationRecord:
        record=self.get_by_execution(execution_id)
        if record is None or not record.progression_authorized:
            raise CanaryReconciliationError('canary progression requires successful immediate reconciliation')
        return record

    def activation_progression_ready(self, activation_id: str) -> bool:
        executions=self.executions.list_for_activation(activation_id)
        submitted=tuple(e for e in executions if e.state=='provider-submitted')
        if not submitted: return False
        return all((r:=self.get_by_execution(e.execution_id)) is not None and r.progression_authorized for e in submitted)

    def get_by_execution(self, execution_id: str) -> CanaryReconciliationRecord | None:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM canary_reconciliations WHERE execution_id=?',(execution_id,)).fetchone()
        if not row: return None
        d=dict(row); d['blockers']=tuple(json.loads(d.pop('blockers_json')))
        for k in ('stop_required','stop_enforced','progression_authorized'): d[k]=bool(d[k])
        return CanaryReconciliationRecord(**d)
