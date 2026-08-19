from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.communications.auron_communications_draft_canary_adapter_v21_601 import CommunicationsDraftCanaryAdapter


class CommunicationsCanaryControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsHealthEvidence:
    evidence_id: str
    provider_id: str
    adapter_id: str
    descriptor_fingerprint: str
    healthy: bool
    observed_at: str


class CommunicationsCanaryHealthCommandCentre:
    """G16 provider health/drift certification plus governed Communications canary controls."""

    def __init__(self, db_path: str | Path, adapter: CommunicationsDraftCanaryAdapter,
                 executions_db_path: str | Path, reconciliation_db_path: str | Path,
                 *, max_age_seconds: int = 300) -> None:
        self.db_path=str(db_path); self.adapter=adapter
        self.executions_db_path=str(executions_db_path); self.reconciliation_db_path=str(reconciliation_db_path)
        self.max_age_seconds=max_age_seconds; self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS communications_canary_health_evidence(
                    evidence_id TEXT PRIMARY KEY,provider_id TEXT NOT NULL,adapter_id TEXT NOT NULL,
                    descriptor_fingerprint TEXT NOT NULL,healthy INTEGER NOT NULL,observed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS communications_canary_command_journal(
                    command_id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,
                    command_text TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL);
            ''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def fingerprint(self) -> str:
        return self._hash(asdict(self.adapter.descriptor()))

    def record_health(self, *, healthy: bool, observed_at: str | None=None) -> CommunicationsHealthEvidence:
        d=self.adapter.descriptor(); ts=observed_at or self._now(); fp=self.fingerprint()
        eid='communications-health-'+self._hash({'provider':d.provider_id,'adapter':d.adapter_id,'fp':fp,'healthy':healthy,'at':ts})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO communications_canary_health_evidence VALUES (?,?,?,?,?,?)',
                (eid,d.provider_id,d.adapter_id,fp,int(healthy),ts))
        return CommunicationsHealthEvidence(eid,d.provider_id,d.adapter_id,fp,healthy,ts)

    def certify_latest_health(self, *, now: str | None=None) -> dict:
        with self._connect() as c:
            row=c.execute('SELECT * FROM communications_canary_health_evidence ORDER BY observed_at DESC,evidence_id DESC LIMIT 1').fetchone()
        if row is None:
            return {'certified':False,'blockers':('health-evidence-missing',),'stale':True,'drift_detected':False}
        d=self.adapter.descriptor(); blockers=[]
        if row['provider_id'] != d.provider_id: blockers.append('provider-identity-drift')
        if row['adapter_id'] != d.adapter_id: blockers.append('adapter-identity-drift')
        if row['descriptor_fingerprint'] != self.fingerprint(): blockers.append('adapter-config-drift')
        if not bool(row['healthy']): blockers.append('provider-unhealthy')
        stale=True
        try:
            seen=datetime.fromisoformat(row['observed_at']); current=datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
            if seen.tzinfo is None: seen=seen.replace(tzinfo=timezone.utc)
            if current.tzinfo is None: current=current.replace(tzinfo=timezone.utc)
            age=(current-seen).total_seconds(); stale=age < 0 or age > self.max_age_seconds
        except ValueError:
            stale=True
        if stale: blockers.append('health-evidence-stale')
        return {'certified':not blockers,'evidence_id':row['evidence_id'],'blockers':tuple(blockers),'stale':stale,
            'drift_detected':any(x.endswith('-drift') for x in blockers),'descriptor_fingerprint':self.fingerprint()}

    @staticmethod
    def _rows(path: str, sql: str) -> tuple[dict,...]:
        c=sqlite3.connect(path); c.row_factory=sqlite3.Row
        try: return tuple(dict(r) for r in c.execute(sql).fetchall())
        except sqlite3.OperationalError: return ()
        finally: c.close()

    def snapshot(self) -> dict:
        health=self.certify_latest_health()
        executions=self._rows(self.executions_db_path,'SELECT * FROM canary_executions ORDER BY created_at DESC,execution_id')
        reconciliations=self._rows(self.reconciliation_db_path,'SELECT * FROM canary_reconciliations ORDER BY reconciled_at DESC,reconciliation_id')
        actions=self._rows(self.adapter.db_path,'SELECT provider_ref,vertical,provider_id,scope,action_key,payload_hash,state,created_at FROM communications_draft_canary_actions ORDER BY created_at DESC,provider_ref')
        stops=self._rows(self.adapter.db_path,'SELECT * FROM communications_draft_canary_stops ORDER BY stopped_at DESC,activation_id')
        alerts=[]
        if not health['certified']:
            alerts.append({'kind':'health','severity':'warning','blockers':health['blockers']})
        for r in reconciliations:
            if not bool(r.get('progression_authorized')):
                alerts.append({'kind':'reconciliation','severity':'warning','execution_id':r.get('execution_id'),'state':r.get('state')})
        for s in stops:
            alerts.append({'kind':'stop','severity':'info','activation_id':s.get('activation_id'),'state':'stopped'})
        return {
            'workspace':'communications-draft-canary',
            'descriptor':asdict(self.adapter.descriptor()),
            'health':health,
            'actions':actions,
            'executions':executions,
            'reconciliations':reconciliations,
            'stops':stops,
            'alerts':tuple(alerts),
            'outbound_send_enabled':False,
            'provider_write_enabled':False,
            'network_transport_enabled':False,
            'production_transport_enabled':False,
            'commands_execute_directly':False,
        }

    def stop(self, activation_id: str, *, actor: str, reason: str='operator-stop') -> dict:
        if not actor.strip(): raise CommunicationsCanaryControlError('actor required')
        self.adapter.stop_canary(activation_id=activation_id,reason=reason)
        return {'activation_id':activation_id,'state':'stopped','outbound_send_enabled':False,'production_transport_enabled':False}

    def record_command(self, command_text: str, *, actor: str) -> dict:
        command=command_text.strip(); operator=actor.strip()
        if not command or not operator: raise CommunicationsCanaryControlError('command and actor required')
        with self._connect() as c:
            cur=c.execute('INSERT INTO communications_canary_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (operator,command,'recorded-not-executed',self._now()))
            command_id=int(cur.lastrowid)
        return {'command_id':command_id,'actor':operator,'command_text':command,'state':'recorded-not-executed'}
