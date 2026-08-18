from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_readonly_canary_adapter_v21_588 import ResearchCanaryAdapterDescriptor


@dataclass(frozen=True)
class ResearchProviderHealthEvidence:
    evidence_id: str
    adapter_id: str
    provider_id: str
    config_fingerprint: str
    healthy: bool
    observed_at: str


@dataclass(frozen=True)
class ResearchProviderHealthDecision:
    certification_id: str
    evidence_id: str
    provider_id: str
    certified: bool
    stale: bool
    drift_detected: bool
    blockers: tuple[str, ...]
    expected_fingerprint: str


class ResearchProviderHealthDriftCertification:
    """G3 persistent health/freshness/config-drift gate for the Research canary adapter."""

    def __init__(self, db_path: str | Path, *, max_age_seconds: int = 300) -> None:
        self.db_path=str(db_path); self.max_age_seconds=max_age_seconds; self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_provider_health_evidence(
                evidence_id TEXT PRIMARY KEY,adapter_id TEXT NOT NULL,provider_id TEXT NOT NULL,
                config_fingerprint TEXT NOT NULL,healthy INTEGER NOT NULL,observed_at TEXT NOT NULL)''')

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @classmethod
    def descriptor_fingerprint(cls, descriptor: ResearchCanaryAdapterDescriptor) -> str:
        return cls._hash(asdict(descriptor))

    def record(self, descriptor: ResearchCanaryAdapterDescriptor, *, healthy: bool,
               observed_at: str | None = None) -> ResearchProviderHealthEvidence:
        ts=observed_at or datetime.now(timezone.utc).isoformat()
        fp=self.descriptor_fingerprint(descriptor)
        eid='research-health-'+self._hash({'adapter':descriptor.adapter_id,'provider':descriptor.provider_id,'fp':fp,'healthy':healthy,'observed_at':ts})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_provider_health_evidence VALUES (?,?,?,?,?,?)',
                (eid,descriptor.adapter_id,descriptor.provider_id,fp,int(healthy),ts))
        return ResearchProviderHealthEvidence(eid,descriptor.adapter_id,descriptor.provider_id,fp,healthy,ts)

    def certify(self, evidence_id: str, descriptor: ResearchCanaryAdapterDescriptor,
                *, now: str | None = None) -> ResearchProviderHealthDecision:
        with self._connect() as c:
            row=c.execute('SELECT * FROM research_provider_health_evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
        expected=self.descriptor_fingerprint(descriptor); blockers=[]
        if row is None:
            blockers.append('health-evidence-missing'); observed=None
        else:
            observed=ResearchProviderHealthEvidence(row['evidence_id'],row['adapter_id'],row['provider_id'],row['config_fingerprint'],bool(row['healthy']),row['observed_at'])
            if observed.adapter_id != descriptor.adapter_id: blockers.append('adapter-identity-drift')
            if observed.provider_id != descriptor.provider_id: blockers.append('provider-identity-drift')
            if observed.config_fingerprint != expected: blockers.append('adapter-config-drift')
            if not observed.healthy: blockers.append('provider-unhealthy')
        stale=True
        if observed is not None:
            try:
                seen=datetime.fromisoformat(observed.observed_at); current=datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
                if seen.tzinfo is None: seen=seen.replace(tzinfo=timezone.utc)
                if current.tzinfo is None: current=current.replace(tzinfo=timezone.utc)
                age=(current-seen).total_seconds(); stale=age < 0 or age > self.max_age_seconds
            except ValueError: stale=True
            if stale: blockers.append('health-evidence-stale')
        drift=any(x.endswith('-drift') for x in blockers)
        cid='research-health-cert-'+self._hash({'evidence':evidence_id,'expected':expected,'blockers':blockers})[:24]
        return ResearchProviderHealthDecision(cid,evidence_id,descriptor.provider_id,not blockers,stale,drift,tuple(blockers),expected)

    @staticmethod
    def require_certified(decision: ResearchProviderHealthDecision) -> ResearchProviderHealthDecision:
        if not decision.certified:
            raise RuntimeError('research provider health/drift certification failed: '+';'.join(decision.blockers))
        return decision
