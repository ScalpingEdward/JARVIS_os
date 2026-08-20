from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler


@dataclass(frozen=True)
class ResearchExternalSandboxHealthSnapshot:
    snapshot_id: str
    contract_id: str
    certification_id: str
    contract_fingerprint: str
    adapter_fingerprint: str
    healthy: bool
    observed_at: str


class ResearchExternalSandboxHealthDriftObservability:
    """H4 operational health/drift read model. It never authorizes transport."""

    def __init__(self, db_path: str | Path, registry: ExternalProviderContractRegistry,
                 adapter: ResearchExternalReadonlySandboxAdapter,
                 reconciler: ResearchExternalSandboxE2EReconciler, *, max_age_seconds: int = 300) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self.adapter=adapter; self.reconciler=reconciler; self.max_age_seconds=max_age_seconds
        self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_external_sandbox_health(
                snapshot_id TEXT PRIMARY KEY,contract_id TEXT NOT NULL,certification_id TEXT NOT NULL,
                contract_fingerprint TEXT NOT NULL,adapter_fingerprint TEXT NOT NULL,
                healthy INTEGER NOT NULL,observed_at TEXT NOT NULL)''')

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def contract_fingerprint(self, contract_id: str) -> str:
        c=self.registry.require_secretless_sandbox(contract_id)
        stable={'contract_id':c.contract_id,'vertical':c.vertical,'provider_id':c.provider_id,'adapter_id':c.adapter_id,
                'environment':c.environment,'allowed_capabilities':c.allowed_capabilities,'read_only':c.read_only,
                'provider_write_enabled':c.provider_write_enabled,'network_transport_enabled':c.network_transport_enabled,
                'production_transport_enabled':c.production_transport_enabled}
        return self._hash(stable)

    def adapter_fingerprint(self) -> str:
        return self._hash(asdict(self.adapter.descriptor()))

    def record(self, *, contract_id: str, certification_id: str, healthy: bool,
               observed_at: str | None = None) -> ResearchExternalSandboxHealthSnapshot:
        cert=self.reconciler.get(certification_id)
        if cert is None or cert.contract_id!=contract_id:
            raise RuntimeError('H4 requires matching H3 certification evidence')
        ts=observed_at or self._now(); cfp=self.contract_fingerprint(contract_id); afp=self.adapter_fingerprint()
        sid='research-external-health-'+self._hash({'contract':contract_id,'cert':certification_id,'cfp':cfp,'afp':afp,'healthy':healthy,'at':ts})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_external_sandbox_health VALUES (?,?,?,?,?,?,?)',
                (sid,contract_id,certification_id,cfp,afp,int(healthy),ts))
        return ResearchExternalSandboxHealthSnapshot(sid,contract_id,certification_id,cfp,afp,healthy,ts)

    def snapshot(self, *, now: str | None = None) -> dict:
        with self._connect() as c:
            row=c.execute('SELECT * FROM research_external_sandbox_health ORDER BY observed_at DESC,snapshot_id DESC LIMIT 1').fetchone()
        blockers=[]
        if row is None:
            return {'operationally_ready':False,'blockers':('health-evidence-missing',),'stale':True,'drift_detected':False,
                    'network_transport_enabled':False,'provider_write_enabled':False,'credential_resolution_enabled':False,'production_transport_enabled':False}
        cert=self.reconciler.get(row['certification_id'])
        if cert is None or cert.status!='certified': blockers.append('h3-certification-missing-or-not-certified')
        if not bool(row['healthy']): blockers.append('provider-unhealthy')
        try:
            seen=datetime.fromisoformat(row['observed_at']); current=datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
            if seen.tzinfo is None: seen=seen.replace(tzinfo=timezone.utc)
            if current.tzinfo is None: current=current.replace(tzinfo=timezone.utc)
            stale=(current-seen).total_seconds()<0 or (current-seen).total_seconds()>self.max_age_seconds
        except ValueError:
            stale=True
        if stale: blockers.append('health-evidence-stale')
        try:
            if row['contract_fingerprint']!=self.contract_fingerprint(row['contract_id']): blockers.append('contract-drift')
        except Exception:
            blockers.append('contract-missing-or-unsafe')
        if row['adapter_fingerprint']!=self.adapter_fingerprint(): blockers.append('adapter-drift')
        drift=any(x.endswith('drift') for x in blockers)
        return {'operationally_ready':not blockers,'snapshot_id':row['snapshot_id'],'contract_id':row['contract_id'],
                'certification_id':row['certification_id'],'healthy':bool(row['healthy']),'stale':stale,
                'drift_detected':drift,'blockers':tuple(blockers),'network_transport_enabled':False,
                'provider_write_enabled':False,'credential_resolution_enabled':False,'production_transport_enabled':False}
