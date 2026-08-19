from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_provider_health_drift_v21_590 import ResearchProviderHealthDriftCertification
from app.research.auron_research_readonly_canary_adapter_v21_588 import ResearchReadonlyCanaryAdapter


class ResearchCanaryCommandCentreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchCanaryCommandEntry:
    command_id: int
    actor: str
    command_text: str
    state: str
    created_at: str


class ResearchCanaryCommandCentre:
    """G4 operational control/read model for the provider-specific Research canary."""

    def __init__(self, db_path: str | Path, adapter: ResearchReadonlyCanaryAdapter,
                 health: ResearchProviderHealthDriftCertification,
                 executions_db_path: str | Path, reconciliation_db_path: str | Path) -> None:
        self.db_path=str(db_path); self.adapter=adapter; self.health=health
        self.executions_db_path=str(executions_db_path); self.reconciliation_db_path=str(reconciliation_db_path)
        self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_canary_command_journal(
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,
                command_text TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL)''')

    @staticmethod
    def _rows(path: str, sql: str) -> tuple[dict,...]:
        c=sqlite3.connect(path); c.row_factory=sqlite3.Row
        try: return tuple(dict(r) for r in c.execute(sql).fetchall())
        except sqlite3.OperationalError: return ()
        finally: c.close()

    def snapshot(self) -> dict:
        descriptor=self.adapter.descriptor()
        health_evidence=self._rows(self.health.db_path,
            'SELECT * FROM research_provider_health_evidence ORDER BY observed_at DESC,evidence_id')
        executions=self._rows(self.executions_db_path,
            'SELECT * FROM canary_executions ORDER BY created_at DESC,execution_id')
        reconciliations=self._rows(self.reconciliation_db_path,
            'SELECT * FROM canary_reconciliations ORDER BY reconciled_at DESC,reconciliation_id')
        stops=self._rows(self.adapter.db_path,
            'SELECT * FROM research_canary_stops ORDER BY stopped_at DESC,activation_id')
        actions=self._rows(self.adapter.db_path,
            'SELECT provider_ref,vertical,provider_id,scope,action_key,payload_hash,state,created_at FROM research_canary_actions ORDER BY created_at DESC,provider_ref')
        alerts=[]
        for e in executions:
            if e.get('state') not in {'provider-submitted'}:
                alerts.append({'kind':'execution','severity':'warning','execution_id':e.get('execution_id'),'state':e.get('state')})
        for r in reconciliations:
            if not bool(r.get('progression_authorized')):
                alerts.append({'kind':'reconciliation','severity':'warning','execution_id':r.get('execution_id'),'state':r.get('state')})
        for s in stops:
            alerts.append({'kind':'stop','severity':'info','activation_id':s.get('activation_id'),'state':'stopped'})
        return {
            'workspace':'research-provider-canary',
            'descriptor':asdict(descriptor),
            'health_evidence':health_evidence,
            'actions':actions,
            'executions':executions,
            'reconciliations':reconciliations,
            'stops':stops,
            'alerts':tuple(alerts),
            'network_transport_enabled':False,
            'production_transport_enabled':False,
            'commands_execute_directly':False,
        }

    def stop(self, activation_id: str, *, actor: str, reason: str='operator-stop') -> dict:
        if not actor.strip(): raise ResearchCanaryCommandCentreError('actor required')
        self.adapter.stop_canary(activation_id=activation_id, reason=reason)
        return {'activation_id':activation_id,'state':'stopped','network_transport_enabled':False,'production_transport_enabled':False}

    def certify_latest_health(self, *, now: str | None=None) -> dict:
        rows=self._rows(self.health.db_path,
            'SELECT evidence_id FROM research_provider_health_evidence ORDER BY observed_at DESC,evidence_id DESC LIMIT 1')
        if not rows: raise ResearchCanaryCommandCentreError('health evidence missing')
        decision=self.health.certify(rows[0]['evidence_id'],self.adapter.descriptor(),now=now)
        return asdict(decision)

    def record_command(self, command_text: str, *, actor: str) -> ResearchCanaryCommandEntry:
        command,operator=command_text.strip(),actor.strip()
        if not command or not operator: raise ResearchCanaryCommandCentreError('command and actor required')
        with self._connect() as c:
            cur=c.execute('INSERT INTO research_canary_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (operator,command,'recorded-not-executed',self._now())); cid=int(cur.lastrowid)
            row=c.execute('SELECT * FROM research_canary_command_journal WHERE command_id=?',(cid,)).fetchone()
        return ResearchCanaryCommandEntry(**dict(row))
