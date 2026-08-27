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
from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_certification_v21_633 import (
    ResearchRealProviderTransportInjectionBoundaryCertification,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesign,
)


@dataclass(frozen=True)
class ResearchRealProviderTransportBindingCertification:
    certification_id: str
    binding_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_binding_verified: bool
    consumption_identity_verified: bool
    scope_budget_verified: bool
    revocation_verified: bool
    zero_transport_network_verified: bool
    certified_at: str


class ResearchRealProviderTransportBindingCertifier:
    """H27 certifies the H26 identity binding only; it injects no transport and enables no network."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_binding_certifications(
                certification_id TEXT PRIMARY KEY,
                binding_id TEXT NOT NULL UNIQUE,
                transport_identity_id TEXT NOT NULL UNIQUE,
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
        bound: ResearchRealProviderBoundTransportIdentity,
        h25: ResearchRealProviderTransportInjectionBoundaryCertification,
        boundary: ResearchRealProviderTransportInjectionBoundaryDesign,
        authorization: ResearchRealProviderTransportInjectionAuthorization,
    ) -> ResearchRealProviderTransportBindingCertification:
        blockers: list[str] = []

        lineage_binding = (
            bound.certification_id == h25.certification_id
            and bound.boundary_id == h25.boundary_id == boundary.boundary_id
            and bound.authorization_id == h25.authorization_id == boundary.authorization_id == authorization.authorization_id
            and h25.status == "certified"
            and not h25.blockers
            and h25.authorization_binding_verified
            and h25.one_time_consumption_verified
            and h25.transport_identity_lifecycle_revocation_verified
            and h25.budget_audit_verified
            and h25.zero_injection_network_verified
        )
        if not lineage_binding:
            blockers.append("h26-h25-h24-h23-lineage-binding-mismatch")

        consumption_identity = (
            bound.authorization_consumed
            and bound.transport_identity_bound
            and bound.revocable
            and bool(bound.transport_identity_id)
            and bound.state in (
                "authorization-consumed-transport-identity-bound-network-disabled",
                "revoked-network-disabled",
            )
        )
        if not consumption_identity:
            blockers.append("authorization-consumption-or-transport-identity-invalid")

        parsed = urlparse(bound.endpoint)
        scope_budget = (
            bound.operator_id == boundary.operator_id == authorization.operator_id
            and bound.provider_id == boundary.provider_id == authorization.provider_id
            and bound.capability == boundary.capability == authorization.capability
            and bound.endpoint == boundary.endpoint == authorization.endpoint
            and bound.allowed_method == boundary.allowed_method == authorization.allowed_method == "GET"
            and bound.request_budget == boundary.request_budget == authorization.request_budget
            and bound.timeout_seconds == boundary.timeout_seconds == authorization.timeout_seconds
            and bound.max_response_bytes == boundary.max_response_bytes == authorization.max_response_bytes
            and bound.transport_ref == boundary.transport_ref == authorization.transport_ref
            and bound.requests_used == 0
            and 1 <= bound.request_budget <= 10
            and 1 <= bound.timeout_seconds <= 30
            and 1 <= bound.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not scope_budget:
            blockers.append("bound-transport-scope-or-budget-invalid")

        revocation = bound.revocable and (
            (not bound.revoked and bound.state == "authorization-consumed-transport-identity-bound-network-disabled")
            or (bound.revoked and bound.state == "revoked-network-disabled")
        )
        if not revocation:
            blockers.append("transport-revocation-state-invalid")

        zero_transport_network = not any(
            (
                bound.transport_injected,
                bound.network_execution_enabled,
                bound.credential_resolution_enabled,
                bound.provider_write_enabled,
                bound.production_transport_enabled,
                authorization.transport_injected,
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
            )
        )
        if not zero_transport_network:
            blockers.append("concrete-transport-network-credential-or-write-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-binding-cert-" + self._hash(
            {
                "binding": bound.binding_id,
                "identity": bound.transport_identity_id,
                "h25": h25.certification_id,
                "authorization": authorization.authorization_id,
                "provider": bound.provider_id,
                "capability": bound.capability,
                "endpoint": bound.endpoint,
                "transport_ref": bound.transport_ref,
            }
        )[:24]
        evidence = {
            "lineage_binding_verified": lineage_binding,
            "consumption_identity_verified": consumption_identity,
            "scope_budget_verified": scope_budget,
            "revocation_verified": revocation,
            "zero_transport_network_verified": zero_transport_network,
            "transport_injected": False,
            "network_execution_enabled": False,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_binding_certifications VALUES (?,?,?,?,?,?,?)",
                (
                    certification_id,
                    bound.binding_id,
                    bound.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderTransportBindingCertification(
            certification_id=certification_id,
            binding_id=bound.binding_id,
            transport_identity_id=bound.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_binding_verified=lineage_binding,
            consumption_identity_verified=consumption_identity,
            scope_budget_verified=scope_budget,
            revocation_verified=revocation,
            zero_transport_network_verified=zero_transport_network,
            certified_at=certified_at,
        )
