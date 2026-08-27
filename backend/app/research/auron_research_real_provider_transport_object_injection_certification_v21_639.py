from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesign,
)
from app.research.auron_research_real_provider_transport_object_injection_design_certification_v21_637 import (
    ResearchRealProviderTransportObjectInjectionDesignCertification,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


@dataclass(frozen=True)
class ResearchRealProviderTransportObjectInjectionCertification:
    certification_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_verified: bool
    uniqueness_identity_verified: bool
    scope_fingerprint_verified: bool
    revocation_verified: bool
    zero_network_verified: bool
    certified_at: str


class ResearchRealProviderTransportObjectInjectionCertifier:
    """H31 certifies H30 injected-object state only; it enables no network execution."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_object_injection_certifications(
                certification_id TEXT PRIMARY KEY,
                injection_id TEXT NOT NULL UNIQUE,
                transport_object_id TEXT NOT NULL UNIQUE,
                transport_identity_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                certified_at TEXT NOT NULL
                )"""
            )

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def certify(
        self,
        injected: ResearchRealProviderInjectedTransportObject,
        h29: ResearchRealProviderTransportObjectInjectionDesignCertification,
        design: ResearchRealProviderTransportObjectInjectionDesign,
        bound: ResearchRealProviderBoundTransportIdentity,
    ) -> ResearchRealProviderTransportObjectInjectionCertification:
        blockers: list[str] = []

        lineage = (
            h29.status == "certified"
            and not h29.blockers
            and h29.lineage_identity_verified
            and h29.contract_scope_verified
            and h29.lifecycle_revocation_verified
            and h29.audit_verified
            and h29.zero_object_network_verified
            and injected.design_certification_id == h29.certification_id
            and injected.injection_design_id == h29.injection_design_id == design.injection_design_id
            and injected.binding_id == h29.binding_id == design.binding_id == bound.binding_id
            and injected.transport_identity_id == h29.transport_identity_id == design.transport_identity_id == bound.transport_identity_id
        )
        if not lineage:
            blockers.append("h30-h29-h28-h27-h26-lineage-mismatch")

        uniqueness_identity = (
            bool(injected.injection_id)
            and bool(injected.transport_object_id)
            and bool(injected.transport_object_fingerprint)
            and injected.transport_object_present
            and injected.transport_object_injected
            and injected.revocable
            and injected.requests_used == 0
            and injected.state in (
                "transport-object-injected-network-disabled",
                "transport-object-revoked-network-disabled",
            )
        )
        if not uniqueness_identity:
            blockers.append("transport-object-identity-or-uniqueness-state-invalid")

        parsed = urlparse(injected.endpoint)
        expected_fingerprint = self._hash({
            "object_id": injected.transport_object_id,
            "provider": injected.provider_id,
            "capability": injected.capability,
            "endpoint": injected.endpoint,
            "method": injected.allowed_method,
            "budget": injected.request_budget,
            "timeout": injected.timeout_seconds,
            "max_response_bytes": injected.max_response_bytes,
            "transport_ref": injected.transport_ref,
        })
        scope_fingerprint = (
            injected.operator_id == design.operator_id == bound.operator_id
            and injected.provider_id == design.provider_id == bound.provider_id
            and injected.capability == design.capability == bound.capability
            and injected.endpoint == design.endpoint == bound.endpoint
            and injected.allowed_method == design.allowed_method == bound.allowed_method == "GET"
            and injected.request_budget == design.request_budget == bound.request_budget
            and injected.timeout_seconds == design.timeout_seconds == bound.timeout_seconds
            and injected.max_response_bytes == design.max_response_bytes == bound.max_response_bytes
            and injected.transport_ref == design.transport_ref == bound.transport_ref
            and injected.transport_object_fingerprint == expected_fingerprint
            and 1 <= injected.request_budget <= 10
            and 1 <= injected.timeout_seconds <= 30
            and 1 <= injected.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not scope_fingerprint:
            blockers.append("transport-object-scope-or-fingerprint-invalid")

        revocation = injected.revocable and (
            (not injected.revoked and injected.state == "transport-object-injected-network-disabled")
            or (injected.revoked and injected.state == "transport-object-revoked-network-disabled")
        )
        if not revocation:
            blockers.append("transport-object-revocation-state-invalid")

        zero_network = not any((
            injected.network_execution_enabled,
            injected.credential_resolution_enabled,
            injected.provider_write_enabled,
            injected.production_transport_enabled,
            bound.network_execution_enabled,
            bound.credential_resolution_enabled,
            bound.provider_write_enabled,
            bound.production_transport_enabled,
        ))
        if not zero_network:
            blockers.append("network-credential-write-or-production-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-object-injection-cert-" + self._hash({
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
            "fingerprint": injected.transport_object_fingerprint,
        })[:24]
        evidence = {
            "lineage_verified": lineage,
            "uniqueness_identity_verified": uniqueness_identity,
            "scope_fingerprint_verified": scope_fingerprint,
            "revocation_verified": revocation,
            "zero_network_verified": zero_network,
            "requests_used": injected.requests_used,
            "network_execution_enabled": False,
        }
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_object_injection_certifications VALUES (?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    injected.injection_id,
                    injected.transport_object_id,
                    injected.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderTransportObjectInjectionCertification(
            certification_id=certification_id,
            injection_id=injected.injection_id,
            transport_object_id=injected.transport_object_id,
            transport_identity_id=injected.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_verified=lineage,
            uniqueness_identity_verified=uniqueness_identity,
            scope_fingerprint_verified=scope_fingerprint,
            revocation_verified=revocation,
            zero_network_verified=zero_network,
            certified_at=certified_at,
        )
