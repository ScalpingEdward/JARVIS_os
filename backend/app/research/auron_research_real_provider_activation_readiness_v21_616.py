from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_readonly_network_boundary_e2e_certification_v21_615 import (
    ResearchReadonlyNetworkE2ECertification,
)


@dataclass(frozen=True)
class ResearchRealProviderActivationReadinessRequest:
    h7_certification: ResearchReadonlyNetworkE2ECertification
    provider_id: str
    provider_environment: str
    endpoint_allowlist: tuple[str, ...]
    credential_provenance: str
    credential_scope_read_only: bool
    operator_id: str
    operator_approved: bool
    rollback_control_ready: bool
    stop_control_ready: bool
    production_transport_requested: bool = False


@dataclass(frozen=True)
class ResearchRealProviderActivationReadinessDecision:
    decision_id: str
    ready_for_separate_activation_design: bool
    blockers: tuple[str, ...]
    real_network_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    requires_separate_provider_adapter: bool
    requires_separate_activation: bool
    decided_at: str


class ResearchRealProviderActivationReadinessService:
    """H8 evidence-only gate. It never configures or activates a real provider transport."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_real_provider_activation_readiness(
                decision_id TEXT PRIMARY KEY,provider_id TEXT NOT NULL,provider_environment TEXT NOT NULL,
                ready INTEGER NOT NULL,blockers_json TEXT NOT NULL,decided_at TEXT NOT NULL)''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def _valid_endpoint(endpoint: str) -> bool:
        try:
            parsed=urlparse(endpoint)
            return parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username and not parsed.password
        except Exception:
            return False

    def evaluate(self, request: ResearchRealProviderActivationReadinessRequest) -> ResearchRealProviderActivationReadinessDecision:
        blockers=[]; cert=request.h7_certification
        if cert.status!='certified' or cert.blockers: blockers.append('h7-certification-not-clean')
        if cert.real_provider_transport_used: blockers.append('h7-real-provider-transport-was-used')
        if cert.provider_writes_observed!=0: blockers.append('h7-provider-write-observed')
        if not cert.budget_enforced: blockers.append('h7-budget-not-enforced')
        if not cert.stop_enforced: blockers.append('h7-stop-not-enforced')

        if not request.provider_id.strip(): blockers.append('provider-id-required')
        if request.provider_environment.strip().lower() not in ('sandbox','test'):
            blockers.append('provider-environment-must-be-nonproduction')
        if not request.endpoint_allowlist: blockers.append('endpoint-allowlist-required')
        elif any(not self._valid_endpoint(e.strip()) for e in request.endpoint_allowlist):
            blockers.append('endpoint-allowlist-invalid')
        elif len(set(request.endpoint_allowlist)) != len(request.endpoint_allowlist):
            blockers.append('endpoint-allowlist-duplicate')
        if not request.credential_provenance.strip(): blockers.append('credential-provenance-required')
        if request.credential_provenance.strip().lower() in ('raw-secret','plaintext','source-code'):
            blockers.append('credential-provenance-unsafe')
        if not request.credential_scope_read_only: blockers.append('credential-scope-not-readonly')
        if not request.operator_id.strip(): blockers.append('operator-id-required')
        if not request.operator_approved: blockers.append('operator-approval-required')
        if not request.rollback_control_ready: blockers.append('rollback-control-not-ready')
        if not request.stop_control_ready: blockers.append('stop-control-not-ready')
        if request.production_transport_requested: blockers.append('production-transport-out-of-scope')

        blockers=tuple(dict.fromkeys(blockers)); ready=not blockers; now=self._now()
        did='research-real-provider-readiness-'+self._hash({'h7':cert.certification_id,'provider':request.provider_id,
            'environment':request.provider_environment,'allowlist':request.endpoint_allowlist,'operator':request.operator_id,
            'blockers':blockers})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_real_provider_activation_readiness VALUES (?,?,?,?,?,?)',
                (did,request.provider_id,request.provider_environment,int(ready),json.dumps(blockers),now))
        return ResearchRealProviderActivationReadinessDecision(did,ready,blockers,False,False,False,False,True,True,now)
