from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_transport_binding_certification_v21_635 import (
    ResearchRealProviderTransportBindingCertification,
)
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesign,
)


@dataclass(frozen=True)
class ResearchRealProviderTransportObjectInjectionDesignCertification:
    certification_id: str
    injection_design_id: str
    binding_certification_id: str
    binding_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_identity_verified: bool
    contract_scope_verified: bool
    lifecycle_revocation_verified: bool
    audit_verified: bool
    zero_object_network_verified: bool
    certified_at: str


class ResearchRealProviderTransportObjectInjectionDesignCertifier:
    """H29 certifies the H28 design only; it cannot accept or inject a transport object."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_object_injection_design_certifications(
                certification_id TEXT PRIMARY KEY,
                injection_design_id TEXT NOT NULL UNIQUE,
                binding_certification_id TEXT NOT NULL,
                binding_id TEXT NOT NULL,
                transport_identity_id TEXT NOT NULL,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                certified_at TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def certify(
        self,
        design: ResearchRealProviderTransportObjectInjectionDesign,
        h27: ResearchRealProviderTransportBindingCertification,
        bound: ResearchRealProviderBoundTransportIdentity,
    ) -> ResearchRealProviderTransportObjectInjectionDesignCertification:
        blockers: list[str] = []

        lineage_identity = (
            h27.status == "certified"
            and not h27.blockers
            and h27.lineage_binding_verified
            and h27.consumption_identity_verified
            and h27.scope_budget_verified
            and h27.revocation_verified
            and h27.zero_transport_network_verified
            and design.binding_certification_id == h27.certification_id
            and design.binding_id == h27.binding_id == bound.binding_id
            and design.transport_identity_id == h27.transport_identity_id == bound.transport_identity_id
            and bound.authorization_consumed
            and bound.transport_identity_bound
            and not bound.revoked
            and bound.state == "authorization-consumed-transport-identity-bound-network-disabled"
        )
        if not lineage_identity:
            blockers.append("h28-h27-h26-lineage-identity-mismatch")

        parsed = urlparse(design.endpoint)
        contract_scope = (
            design.operator_id == bound.operator_id
            and design.provider_id == bound.provider_id
            and design.capability == bound.capability
            and design.endpoint == bound.endpoint
            and design.allowed_method == bound.allowed_method == "GET"
            and design.request_budget == bound.request_budget
            and design.requests_used == bound.requests_used == 0
            and design.timeout_seconds == bound.timeout_seconds
            and design.max_response_bytes == bound.max_response_bytes
            and design.transport_ref == bound.transport_ref
            and 1 <= design.request_budget <= 10
            and 1 <= design.timeout_seconds <= 30
            and 1 <= design.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
            and design.transport_ref.startswith("transportref://")
            and len(design.transport_ref) > len("transportref://")
            and design.transport_object_contract
            == "callable-readonly-transport-object-with-exact-endpoint-capability-budget-timeout-response-bounds"
            and design.identity_binding_semantics
            == "transport-object-must-bind-exactly-to-h27-certified-transport-identity-id"
            and design.injection_semantics
            == "separate-gate-may-attach-one-object-to-one-certified-identity-without-network-execution"
        )
        if not contract_scope:
            blockers.append("transport-object-contract-or-scope-invalid")

        lifecycle_revocation = (
            design.lifecycle_semantics
            == "injected-object-remains-network-disabled-until-separate-execution-gate"
            and design.revocation_semantics
            == "revocation-invalidates-object-before-any-network-execution"
            and design.state == "designed-object-absent-not-injected-network-disabled"
            and bound.revocable
            and not bound.revoked
        )
        if not lifecycle_revocation:
            blockers.append("transport-object-lifecycle-or-revocation-invalid")

        audit = (
            design.audit_semantics
            == "metadata-and-hashes-only-no-raw-credentials-request-or-response-bodies"
        )
        if not audit:
            blockers.append("transport-object-audit-semantics-invalid")

        zero_object_network = not any(
            (
                design.transport_object_present,
                design.transport_object_injected,
                design.network_execution_enabled,
                design.credential_resolution_enabled,
                design.provider_write_enabled,
                design.production_transport_enabled,
                bound.transport_injected,
                bound.network_execution_enabled,
                bound.credential_resolution_enabled,
                bound.provider_write_enabled,
                bound.production_transport_enabled,
            )
        )
        if not zero_object_network:
            blockers.append("transport-object-network-credential-or-write-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-object-injection-design-cert-" + self._hash(
            {
                "design": design.injection_design_id,
                "h27": h27.certification_id,
                "binding": bound.binding_id,
                "identity": bound.transport_identity_id,
                "provider": design.provider_id,
                "capability": design.capability,
                "endpoint": design.endpoint,
                "transport_ref": design.transport_ref,
            }
        )[:24]
        evidence = {
            "lineage_identity_verified": lineage_identity,
            "contract_scope_verified": contract_scope,
            "lifecycle_revocation_verified": lifecycle_revocation,
            "audit_verified": audit,
            "zero_object_network_verified": zero_object_network,
            "transport_object_present": False,
            "transport_object_injected": False,
            "network_execution_enabled": False,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_object_injection_design_certifications VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    design.injection_design_id,
                    h27.certification_id,
                    bound.binding_id,
                    bound.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderTransportObjectInjectionDesignCertification(
            certification_id=certification_id,
            injection_design_id=design.injection_design_id,
            binding_certification_id=h27.certification_id,
            binding_id=bound.binding_id,
            transport_identity_id=bound.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_identity_verified=lineage_identity,
            contract_scope_verified=contract_scope,
            lifecycle_revocation_verified=lifecycle_revocation,
            audit_verified=audit,
            zero_object_network_verified=zero_object_network,
            certified_at=certified_at,
        )
