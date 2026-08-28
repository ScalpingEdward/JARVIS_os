from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_network_execution_authorization_certification_v21_643 import (
    ResearchRealProviderNetworkExecutionAuthorizationCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionBoundaryCertification:
    certification_id: str
    boundary_design_id: str
    authorization_certification_id: str
    authorization_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_identity_verified: bool
    consumption_expiry_revocation_verified: bool
    readonly_scope_verified: bool
    audit_verified: bool
    zero_consumed_reserved_network_verified: bool
    certified_at: str


class ResearchRealProviderNetworkExecutionBoundaryCertifier:
    """H37 certifies H36 design semantics only; it never consumes authorization or executes traffic."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_boundary_certifications(
                certification_id TEXT PRIMARY KEY,
                boundary_design_id TEXT NOT NULL UNIQUE,
                authorization_certification_id TEXT NOT NULL,
                authorization_id TEXT NOT NULL,
                injection_id TEXT NOT NULL,
                transport_object_id TEXT NOT NULL,
                transport_identity_id TEXT NOT NULL,
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
        design: ResearchRealProviderNetworkExecutionBoundaryDesign,
        h35: ResearchRealProviderNetworkExecutionAuthorizationCertification,
        authorization: ResearchRealProviderNetworkExecutionAuthorization,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionBoundaryCertification:
        blockers: list[str] = []

        lineage_identity = (
            h35.status == "certified"
            and not h35.blockers
            and h35.lineage_identity_verified
            and h35.ttl_expiry_verified
            and h35.one_shot_scope_verified
            and h35.revocation_verified
            and h35.zero_consumed_network_verified
            and design.authorization_certification_id == h35.certification_id
            and design.authorization_id == h35.authorization_id == authorization.authorization_id
            and design.injection_id == h35.injection_id == authorization.injection_id == injected.injection_id
            and design.transport_object_id == h35.transport_object_id == authorization.transport_object_id == injected.transport_object_id
            and design.transport_identity_id == h35.transport_identity_id == authorization.transport_identity_id == injected.transport_identity_id
        )
        if not lineage_identity:
            blockers.append("h36-h35-h34-h33-h32-h31-h30-lineage-identity-mismatch")

        consumption_expiry_revocation = (
            design.consumption_limit == 1
            and design.consumption_semantics
            == "exactly-once-consume-one-clean-h35-certified-authorization-before-any-network-call"
            and design.execution_semantics
            == "later-explicit-execution-gate-may-consume-and-attempt-at-most-one-readonly-request"
            and design.expiry_semantics
            == "authorization-must-be-unexpired-at-consumption-and-fails-closed-after-expiry"
            and design.revocation_semantics
            == "authorization-or-transport-revocation-invalidates-boundary-before-consumption"
            and authorization.authorization_issued
            and not authorization.authorization_consumed
            and authorization.revocable
            and not authorization.revoked
            and injected.revocable
            and not injected.revoked
            and design.authorization_expires_at == authorization.expires_at
        )
        if not consumption_expiry_revocation:
            blockers.append("boundary-consumption-expiry-or-revocation-semantics-invalid")

        parsed = urlparse(design.endpoint)
        readonly_scope = (
            design.operator_id == authorization.operator_id == injected.operator_id
            and design.provider_id == authorization.provider_id == injected.provider_id
            and design.capability == authorization.capability == injected.capability
            and design.endpoint == authorization.endpoint == injected.endpoint
            and design.allowed_method == authorization.allowed_method == injected.allowed_method == "GET"
            and design.request_budget == authorization.request_budget == injected.request_budget
            and design.requests_used == authorization.requests_used == injected.requests_used == 0
            and design.timeout_seconds == authorization.timeout_seconds == injected.timeout_seconds
            and design.max_response_bytes == authorization.max_response_bytes == injected.max_response_bytes
            and design.transport_ref == authorization.transport_ref == injected.transport_ref
            and 1 <= design.request_budget <= 10
            and 1 <= design.timeout_seconds <= 30
            and 1 <= design.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not readonly_scope:
            blockers.append("boundary-readonly-scope-invalid")

        audit = design.audit_semantics == "append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies"
        if not audit:
            blockers.append("boundary-audit-semantics-invalid")

        zero_state = (
            design.state == "designed-authorization-unconsumed-request-unreserved-network-disabled"
            and not any((
                design.authorization_consumed,
                design.request_reserved,
                design.network_execution_enabled,
                design.credential_resolution_enabled,
                design.provider_write_enabled,
                design.production_transport_enabled,
                authorization.authorization_consumed,
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
                injected.network_execution_enabled,
                injected.credential_resolution_enabled,
                injected.provider_write_enabled,
                injected.production_transport_enabled,
            ))
        )
        if not zero_state:
            blockers.append("boundary-consumed-reserved-or-network-state-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-network-execution-boundary-cert-" + self._hash({
            "design": design.boundary_design_id,
            "h35": h35.certification_id,
            "authorization": authorization.authorization_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
        })[:24]
        evidence = {
            "lineage_identity_verified": lineage_identity,
            "consumption_expiry_revocation_verified": consumption_expiry_revocation,
            "readonly_scope_verified": readonly_scope,
            "audit_verified": audit,
            "zero_consumed_reserved_network_verified": zero_state,
            "authorization_consumed": False,
            "request_reserved": False,
            "network_execution_enabled": False,
        }
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_boundary_certifications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    design.boundary_design_id,
                    h35.certification_id,
                    authorization.authorization_id,
                    injected.injection_id,
                    injected.transport_object_id,
                    injected.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderNetworkExecutionBoundaryCertification(
            certification_id=certification_id,
            boundary_design_id=design.boundary_design_id,
            authorization_certification_id=h35.certification_id,
            authorization_id=authorization.authorization_id,
            injection_id=injected.injection_id,
            transport_object_id=injected.transport_object_id,
            transport_identity_id=injected.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_identity_verified=lineage_identity,
            consumption_expiry_revocation_verified=consumption_expiry_revocation,
            readonly_scope_verified=readonly_scope,
            audit_verified=audit,
            zero_consumed_reserved_network_verified=zero_state,
            certified_at=certified_at,
        )
