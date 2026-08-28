from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_certification_v21_645 import (
    ResearchRealProviderNetworkExecutionBoundaryCertification,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_network_execution_gate_v21_646 import (
    ResearchRealProviderNetworkExecutionReservation,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionGateCertification:
    certification_id: str
    reservation_id: str
    boundary_certification_id: str
    boundary_design_id: str
    authorization_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_identity_verified: bool
    exactly_once_reservation_verified: bool
    expiry_revocation_verified: bool
    readonly_scope_verified: bool
    zero_provider_traffic_verified: bool
    certified_at: str


class ResearchRealProviderNetworkExecutionGateCertifier:
    """H39 certifies the H38 consumed/reserved state; it performs no provider traffic."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_gate_certifications(
                certification_id TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL UNIQUE,
                boundary_certification_id TEXT NOT NULL,
                boundary_design_id TEXT NOT NULL,
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
    def _dt(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def certify(
        self,
        reservation: ResearchRealProviderNetworkExecutionReservation,
        h37: ResearchRealProviderNetworkExecutionBoundaryCertification,
        design: ResearchRealProviderNetworkExecutionBoundaryDesign,
        authorization: ResearchRealProviderNetworkExecutionAuthorization,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionGateCertification:
        blockers: list[str] = []

        lineage_identity = (
            h37.status == "certified"
            and not h37.blockers
            and h37.lineage_identity_verified
            and h37.consumption_expiry_revocation_verified
            and h37.readonly_scope_verified
            and h37.audit_verified
            and h37.zero_consumed_reserved_network_verified
            and reservation.boundary_certification_id == h37.certification_id
            and reservation.boundary_design_id == h37.boundary_design_id == design.boundary_design_id
            and reservation.authorization_id == h37.authorization_id == design.authorization_id == authorization.authorization_id
            and reservation.injection_id == h37.injection_id == design.injection_id == authorization.injection_id == injected.injection_id
            and reservation.transport_object_id == h37.transport_object_id == design.transport_object_id == authorization.transport_object_id == injected.transport_object_id
            and reservation.transport_identity_id == h37.transport_identity_id == design.transport_identity_id == authorization.transport_identity_id == injected.transport_identity_id
        )
        if not lineage_identity:
            blockers.append("h38-h37-h36-h35-h34-h33-h32-h31-h30-lineage-identity-mismatch")

        exactly_once = (
            design.consumption_limit == 1
            and reservation.authorization_consumed
            and reservation.request_reserved
            and reservation.reserved_request_count == 1
            and reservation.requests_used == 0
            and reservation.state in (
                "authorization-consumed-request-reserved-network-disabled",
                "reservation-revoked-network-disabled",
            )
        )
        if not exactly_once:
            blockers.append("authorization-consumption-or-single-request-reservation-invalid")

        try:
            reserved_at = self._dt(reservation.reserved_at)
            expires_at = self._dt(reservation.authorization_expires_at)
            expiry_ok = reserved_at < expires_at and reservation.authorization_expires_at == design.authorization_expires_at == authorization.expires_at
        except (TypeError, ValueError):
            expiry_ok = False
        expiry_revocation = (
            expiry_ok
            and reservation.revocable
            and (
                (not reservation.revoked and reservation.state == "authorization-consumed-request-reserved-network-disabled")
                or (reservation.revoked and reservation.state == "reservation-revoked-network-disabled")
            )
            and injected.revocable
        )
        if not expiry_revocation:
            blockers.append("reservation-expiry-or-revocation-state-invalid")

        parsed = urlparse(reservation.endpoint)
        readonly_scope = (
            reservation.operator_id == design.operator_id == authorization.operator_id == injected.operator_id
            and reservation.provider_id == design.provider_id == authorization.provider_id == injected.provider_id
            and reservation.capability == design.capability == authorization.capability == injected.capability
            and reservation.endpoint == design.endpoint == authorization.endpoint == injected.endpoint
            and reservation.allowed_method == design.allowed_method == authorization.allowed_method == injected.allowed_method == "GET"
            and reservation.request_budget == design.request_budget == authorization.request_budget == injected.request_budget
            and reservation.timeout_seconds == design.timeout_seconds == authorization.timeout_seconds == injected.timeout_seconds
            and reservation.max_response_bytes == design.max_response_bytes == authorization.max_response_bytes == injected.max_response_bytes
            and reservation.transport_ref == design.transport_ref == authorization.transport_ref == injected.transport_ref
            and 1 <= reservation.request_budget <= 10
            and 1 <= reservation.timeout_seconds <= 30
            and 1 <= reservation.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not readonly_scope:
            blockers.append("reserved-request-readonly-scope-invalid")

        zero_provider_traffic = (
            reservation.requests_used == 0
            and not any((
                reservation.network_execution_enabled,
                reservation.credential_resolution_enabled,
                reservation.provider_write_enabled,
                reservation.production_transport_enabled,
                design.network_execution_enabled,
                design.credential_resolution_enabled,
                design.provider_write_enabled,
                design.production_transport_enabled,
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
        if not zero_provider_traffic:
            blockers.append("provider-traffic-credential-write-or-production-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-network-execution-gate-cert-" + self._hash({
            "reservation": reservation.reservation_id,
            "h37": h37.certification_id,
            "boundary": design.boundary_design_id,
            "authorization": authorization.authorization_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
        })[:24]
        evidence = {
            "lineage_identity_verified": lineage_identity,
            "exactly_once_reservation_verified": exactly_once,
            "expiry_revocation_verified": expiry_revocation,
            "readonly_scope_verified": readonly_scope,
            "zero_provider_traffic_verified": zero_provider_traffic,
            "authorization_consumed": reservation.authorization_consumed,
            "request_reserved": reservation.request_reserved,
            "reserved_request_count": reservation.reserved_request_count,
            "requests_used": reservation.requests_used,
            "network_execution_enabled": reservation.network_execution_enabled,
        }
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_gate_certifications VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    reservation.reservation_id,
                    h37.certification_id,
                    design.boundary_design_id,
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

        return ResearchRealProviderNetworkExecutionGateCertification(
            certification_id=certification_id,
            reservation_id=reservation.reservation_id,
            boundary_certification_id=h37.certification_id,
            boundary_design_id=design.boundary_design_id,
            authorization_id=authorization.authorization_id,
            injection_id=injected.injection_id,
            transport_object_id=injected.transport_object_id,
            transport_identity_id=injected.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_identity_verified=lineage_identity,
            exactly_once_reservation_verified=exactly_once,
            expiry_revocation_verified=expiry_revocation,
            readonly_scope_verified=readonly_scope,
            zero_provider_traffic_verified=zero_provider_traffic,
            certified_at=certified_at,
        )
