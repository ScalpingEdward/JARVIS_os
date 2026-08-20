from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_health_drift_observability_v21_612 import ResearchExternalSandboxHealthDriftObservability


@dataclass(frozen=True)
class ResearchNetworkTransportAuthorizationRequest:
    contract_id: str
    operator_id: str
    requested_capability: str
    operator_approved: bool
    rollback_control_ready: bool
    stop_control_ready: bool
    credential_reference_present: bool


@dataclass(frozen=True)
class ResearchNetworkTransportAuthorizationDecision:
    decision_id: str
    contract_id: str
    requested_capability: str
    authorized: bool
    blockers: tuple[str, ...]
    network_transport_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    requires_separate_activation: bool
    decided_at: str


class ResearchNetworkTransportAuthorizationService:
    """H5 decision-only gate for future Research read-only network transport.

    Authorization here means the evidence is sufficient to proceed to a later transport-boundary
    implementation/activation step. This class never resolves credentials, opens a network client,
    enables transport, performs provider writes, or changes the H1 contract flags.
    """

    def __init__(self, db_path: str | Path, registry: ExternalProviderContractRegistry,
                 adapter: ResearchExternalReadonlySandboxAdapter,
                 observability: ResearchExternalSandboxHealthDriftObservability) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self.adapter=adapter; self.observability=observability; self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_network_transport_authorization(
                decision_id TEXT PRIMARY KEY,contract_id TEXT NOT NULL,requested_capability TEXT NOT NULL,
                operator_id TEXT NOT NULL,authorized INTEGER NOT NULL,blockers_json TEXT NOT NULL,
                decided_at TEXT NOT NULL)''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def evaluate(self, request: ResearchNetworkTransportAuthorizationRequest, *, now: str | None = None) -> ResearchNetworkTransportAuthorizationDecision:
        blockers=[]; d=self.adapter.descriptor()
        try:
            contract=self.registry.require_secretless_sandbox(request.contract_id)
        except Exception:
            contract=None; blockers.append('contract-missing-or-unsafe')

        if request.contract_id != self.adapter.contract_id: blockers.append('adapter-contract-mismatch')
        if contract is not None:
            if (contract.vertical,contract.provider_id,contract.adapter_id,contract.environment)!=(d.vertical,d.provider_id,d.adapter_id,d.environment): blockers.append('contract-identity-mismatch')
            if request.requested_capability not in contract.allowed_capabilities: blockers.append('capability-not-in-contract')
            if request.requested_capability not in d.allowed_actions: blockers.append('capability-not-in-adapter')
            if contract.provider_write_enabled or contract.production_transport_enabled: blockers.append('unsafe-contract-capability')
            if contract.network_transport_enabled: blockers.append('h1-contract-must-remain-transport-disabled')
            actual_ref_present=contract.credential_ref is not None
            if actual_ref_present != request.credential_reference_present: blockers.append('credential-reference-state-mismatch')
            if not actual_ref_present: blockers.append('credential-reference-missing')

        obs=self.observability.snapshot(now=now)
        if not obs.get('operationally_ready',False): blockers.append('h4-operational-readiness-blocked')
        if obs.get('drift_detected'): blockers.append('h4-drift-detected')
        if obs.get('stale'): blockers.append('h4-health-evidence-stale')
        if obs.get('network_transport_enabled') or obs.get('provider_write_enabled') or obs.get('credential_resolution_enabled') or obs.get('production_transport_enabled'):
            blockers.append('preexisting-live-capability-detected')
        if not request.operator_id.strip(): blockers.append('operator-id-required')
        if not request.operator_approved: blockers.append('operator-approval-required')
        if not request.rollback_control_ready: blockers.append('rollback-control-not-ready')
        if not request.stop_control_ready: blockers.append('stop-control-not-ready')

        blockers=tuple(dict.fromkeys(blockers)); authorized=not blockers; decided=self._now()
        did='research-network-auth-'+self._hash({'contract':request.contract_id,'operator':request.operator_id,'capability':request.requested_capability,'blockers':blockers})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_network_transport_authorization VALUES (?,?,?,?,?,?,?)',
                (did,request.contract_id,request.requested_capability,request.operator_id,int(authorized),json.dumps(blockers),decided))
        return ResearchNetworkTransportAuthorizationDecision(did,request.contract_id,request.requested_capability,authorized,blockers,
            False,False,False,False,True,decided)
