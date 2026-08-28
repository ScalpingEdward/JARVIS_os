from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_network_execution_gate_certification_v21_647 import (
    ResearchRealProviderNetworkExecutionGateCertification,
)
from app.research.auron_research_real_provider_network_execution_gate_v21_646 import (
    ResearchRealProviderNetworkExecutionReservation,
)


class ResearchRealProviderRequestExecutionDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderRequestExecutionDesign:
    request_execution_design_id: str
    gate_certification_id: str
    reservation_id: str
    boundary_certification_id: str
    boundary_design_id: str
    authorization_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    immutable_request_id: str
    operator_id: str
    provider_id: str
    capability: str
    endpoint: str
    allowed_method: str
    request_budget: int
    requests_used: int
    timeout_seconds: int
    max_response_bytes: int
    transport_ref: str
    authorization_expires_at: str
    transport_call_signature: str
    request_identity_semantics: str
    response_bound_semantics: str
    timeout_error_semantics: str
    audit_semantics: str
    reconciliation_semantics: str
    execution_semantics: str
    state: str
    authorization_consumed: bool
    request_reserved: bool
    reserved_request_count: int
    request_executed: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ResearchRealProviderRequestExecutionDesignRegistry:
    """H40 defines the future single-request provider-call contract.

    Design-only: no provider call, credential resolution, response handling or production
    transport activation occurs here. One clean H39-certified reservation is bound to one
    immutable request identity and one fail-closed read-only transport-call contract.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_request_execution_designs(
                request_execution_design_id TEXT PRIMARY KEY,
                gate_certification_id TEXT NOT NULL UNIQUE,
                reservation_id TEXT NOT NULL UNIQUE,
                boundary_certification_id TEXT NOT NULL,
                boundary_design_id TEXT NOT NULL,
                authorization_id TEXT NOT NULL,
                injection_id TEXT NOT NULL,
                transport_object_id TEXT NOT NULL,
                transport_identity_id TEXT NOT NULL,
                immutable_request_id TEXT NOT NULL UNIQUE,
                operator_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                allowed_method TEXT NOT NULL,
                request_budget INTEGER NOT NULL,
                requests_used INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                max_response_bytes INTEGER NOT NULL,
                transport_ref TEXT NOT NULL,
                authorization_expires_at TEXT NOT NULL,
                transport_call_signature TEXT NOT NULL,
                request_identity_semantics TEXT NOT NULL,
                response_bound_semantics TEXT NOT NULL,
                timeout_error_semantics TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                reconciliation_semantics TEXT NOT NULL,
                execution_semantics TEXT NOT NULL,
                state TEXT NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                request_reserved INTEGER NOT NULL,
                reserved_request_count INTEGER NOT NULL,
                request_executed INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL
                )"""
            )

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def register(
        self,
        certification: ResearchRealProviderNetworkExecutionGateCertification,
        reservation: ResearchRealProviderNetworkExecutionReservation,
    ) -> ResearchRealProviderRequestExecutionDesign:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderRequestExecutionDesignError("clean H39 certification required")
        if not all((
            certification.lineage_identity_verified,
            certification.exactly_once_reservation_verified,
            certification.expiry_revocation_verified,
            certification.readonly_scope_verified,
            certification.zero_provider_traffic_verified,
        )):
            raise ResearchRealProviderRequestExecutionDesignError("H39 certification invariants incomplete")
        if (
            certification.reservation_id != reservation.reservation_id
            or certification.boundary_certification_id != reservation.boundary_certification_id
            or certification.boundary_design_id != reservation.boundary_design_id
            or certification.authorization_id != reservation.authorization_id
            or certification.injection_id != reservation.injection_id
            or certification.transport_object_id != reservation.transport_object_id
            or certification.transport_identity_id != reservation.transport_identity_id
        ):
            raise ResearchRealProviderRequestExecutionDesignError("H39/H38 lineage mismatch")
        if not reservation.authorization_consumed:
            raise ResearchRealProviderRequestExecutionDesignError("consumed authorization required")
        if not reservation.request_reserved or reservation.reserved_request_count != 1:
            raise ResearchRealProviderRequestExecutionDesignError("exactly one reserved request required")
        if reservation.requests_used != 0:
            raise ResearchRealProviderRequestExecutionDesignError("reserved request must remain unused")
        if reservation.revoked or not reservation.revocable:
            raise ResearchRealProviderRequestExecutionDesignError("active revocable reservation required")
        if reservation.state != "authorization-consumed-request-reserved-network-disabled":
            raise ResearchRealProviderRequestExecutionDesignError("reservation state not designable")
        parsed = urlparse(reservation.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderRequestExecutionDesignError("unsafe endpoint")
        if reservation.allowed_method != "GET":
            raise ResearchRealProviderRequestExecutionDesignError("H40 remains read-only GET only")
        if not 1 <= reservation.request_budget <= 10:
            raise ResearchRealProviderRequestExecutionDesignError("bounded request budget required")
        if not 1 <= reservation.timeout_seconds <= 30:
            raise ResearchRealProviderRequestExecutionDesignError("timeout must be 1..30 seconds")
        if not 1 <= reservation.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderRequestExecutionDesignError("max response bytes must be 1..1048576")
        if any((
            reservation.network_execution_enabled,
            reservation.credential_resolution_enabled,
            reservation.provider_write_enabled,
            reservation.production_transport_enabled,
        )):
            raise ResearchRealProviderRequestExecutionDesignError("H40 requires zero provider execution state")

        immutable_request_id = "research-real-request-" + self._hash({
            "reservation": reservation.reservation_id,
            "provider": reservation.provider_id,
            "capability": reservation.capability,
            "endpoint": reservation.endpoint,
            "method": reservation.allowed_method,
            "transport_ref": reservation.transport_ref,
        })[:24]
        design_id = "research-real-request-execution-design-" + self._hash({
            "h39": certification.certification_id,
            "reservation": reservation.reservation_id,
            "request": immutable_request_id,
            "object": reservation.transport_object_id,
            "identity": reservation.transport_identity_id,
        })[:24]
        transport_call_signature = (
            "GET(endpoint, transport_ref, timeout_seconds, max_response_bytes, immutable_request_id)"
        )
        values = (
            design_id,
            certification.certification_id,
            reservation.reservation_id,
            reservation.boundary_certification_id,
            reservation.boundary_design_id,
            reservation.authorization_id,
            reservation.injection_id,
            reservation.transport_object_id,
            reservation.transport_identity_id,
            immutable_request_id,
            reservation.operator_id,
            reservation.provider_id,
            reservation.capability,
            reservation.endpoint,
            reservation.allowed_method,
            reservation.request_budget,
            reservation.requests_used,
            reservation.timeout_seconds,
            reservation.max_response_bytes,
            reservation.transport_ref,
            reservation.authorization_expires_at,
            transport_call_signature,
            "immutable-id-derived-from-certified-reservation-and-exact-readonly-scope",
            "response-body-must-not-exceed-certified-max-response-bytes",
            "single-attempt-fail-closed-timeout-or-transport-error-no-automatic-retry",
            "append-only-metadata-hashes-status-timing-no-raw-credentials-or-response-body",
            "request-id-correlates-reservation-attempt-result-and-terminal-status-exactly-once",
            "later-explicit-execution-gate-may-attempt-one-readonly-provider-call-only",
            "designed-reservation-certified-request-unexecuted-network-disabled",
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            datetime.now(timezone.utc).isoformat(),
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_request_execution_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_request_execution_designs WHERE gate_certification_id=?",
                (certification.certification_id,),
            ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_consumed",
            "request_reserved",
            "request_executed",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderRequestExecutionDesign(**data)
