from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_real_provider_activation_readiness_v21_616 import (
    ResearchRealProviderActivationReadinessDecision,
)
from app.research.auron_research_real_provider_adapter_contract_v21_617 import (
    ResearchRealProviderAdapterContractRegistry,
)


@dataclass(frozen=True)
class ResearchRealProviderAdapterContractCertificationRequest:
    h8_decision: ResearchRealProviderActivationReadinessDecision
    contract_design_id: str
    expected_provider_name: str
    expected_provider_environment: str
    endpoint_allowlist: tuple[str, ...]


@dataclass(frozen=True)
class ResearchRealProviderAdapterContractCertification:
    certification_id: str
    contract_design_id: str
    status: str
    blockers: tuple[str, ...]
    real_network_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    requires_separate_adapter_implementation: bool
    certified_at: str


class ResearchRealProviderAdapterContractCertificationService:
    """H10 structurally certifies the H9 design against clean H8 readiness evidence.

    This layer performs no network I/O and implements no provider client or credential resolver.
    """

    def __init__(self, db_path: str | Path, registry: ResearchRealProviderAdapterContractRegistry) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_real_provider_contract_certifications(
                certification_id TEXT PRIMARY KEY,contract_design_id TEXT NOT NULL,status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,certified_at TEXT NOT NULL)''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def certify(self, request: ResearchRealProviderAdapterContractCertificationRequest) -> ResearchRealProviderAdapterContractCertification:
        blockers=[]; d=request.h8_decision
        if not d.ready_for_separate_activation_design or d.blockers:
            blockers.append('h8-readiness-not-clean')
        if any((d.real_network_enabled,d.credential_resolution_enabled,d.provider_write_enabled,d.production_transport_enabled)):
            blockers.append('h8-preactivation-safety-violated')
        if not d.requires_separate_provider_adapter or not d.requires_separate_activation:
            blockers.append('h8-separate-boundaries-not-required')

        contract=self.registry.get(request.contract_design_id)
        if contract is None:
            blockers.append('h9-contract-missing')
        else:
            if contract.provider_name != request.expected_provider_name:
                blockers.append('provider-identity-mismatch')
            if contract.provider_environment != request.expected_provider_environment:
                blockers.append('provider-environment-mismatch')
            if contract.vertical != 'research': blockers.append('vertical-mismatch')
            if contract.provider_environment.strip().lower() in ('production','prod','live'):
                blockers.append('production-environment-forbidden')
            endpoints=tuple(b.endpoint_template for b in contract.endpoint_bindings)
            if set(endpoints) != set(request.endpoint_allowlist):
                blockers.append('endpoint-allowlist-mismatch')
            if any(b.method.upper()!='GET' for b in contract.endpoint_bindings):
                blockers.append('non-get-binding-detected')
            if any(b.capability not in self.registry.ALLOWED_CAPABILITIES for b in contract.endpoint_bindings):
                blockers.append('unapproved-capability-detected')
            if contract.credential_resolver.credential_ref_scheme!='secretref://': blockers.append('credential-ref-scheme-unsafe')
            if contract.credential_resolver.credential_scope!='read-only': blockers.append('credential-scope-not-readonly')
            if contract.credential_resolver.raw_secret_persistence_allowed or contract.credential_resolver.raw_secret_logging_allowed:
                blockers.append('raw-secret-handling-unsafe')
            if contract.audit.persist_raw_credential or contract.audit.persist_raw_response_body:
                blockers.append('audit-raw-material-persistence-unsafe')
            if not (contract.audit.persist_request_metadata and contract.audit.persist_status_code and contract.audit.persist_response_hash):
                blockers.append('audit-minimum-evidence-missing')
            if any((contract.network_implementation_included,contract.provider_client_included,
                    contract.write_methods_allowed,contract.production_transport_allowed)):
                blockers.append('h9-design-only-boundary-violated')

        blockers=tuple(dict.fromkeys(blockers)); status='certified' if not blockers else 'blocked'; now=self._now()
        cid='research-provider-contract-cert-'+self._hash({'h8':d.decision_id,'design':request.contract_design_id,'blockers':blockers})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_real_provider_contract_certifications VALUES (?,?,?,?,?)',
                (cid,request.contract_design_id,status,json.dumps(blockers),now))
        return ResearchRealProviderAdapterContractCertification(cid,request.contract_design_id,status,blockers,
            False,False,False,False,True,now)
