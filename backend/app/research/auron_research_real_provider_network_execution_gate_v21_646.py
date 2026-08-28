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
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


class ResearchRealProviderNetworkExecutionGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionReservation:
    reservation_id: str
    boundary_certification_id: str
    boundary_design_id: str
    authorization_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
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
    state: str
    authorization_consumed: bool
    request_reserved: bool
    reserved_request_count: int
    revocable: bool
    revoked: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    reserved_at: str


class ResearchRealProviderNetworkExecutionGate:
    """H38 consumes one clean H37-certified authorization and reserves one read-only request.

    This gate stops before provider traffic. It never resolves credentials, performs networking,
    writes to a provider, or enables production transport. Actual request execution remains a
    later explicit step.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_reservations(
                reservation_id TEXT PRIMARY KEY,
                boundary_certification_id TEXT NOT NULL UNIQUE,
                boundary_design_id TEXT NOT NULL UNIQUE,
                authorization_id TEXT NOT NULL UNIQUE,
                injection_id TEXT NOT NULL,
                transport_object_id TEXT NOT NULL,
                transport_identity_id TEXT NOT NULL,
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
                state TEXT NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                request_reserved INTEGER NOT NULL,
                reserved_request_count INTEGER NOT NULL,
                revocable INTEGER NOT NULL,
                revoked INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                reserved_at TEXT NOT NULL
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
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def reserve(
        self,
        certification: ResearchRealProviderNetworkExecutionBoundaryCertification,
        design: ResearchRealProviderNetworkExecutionBoundaryDesign,
        authorization: ResearchRealProviderNetworkExecutionAuthorization,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionReservation:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderNetworkExecutionGateError("clean H37 certification required")
        if not all((
            certification.lineage_identity_verified,
            certification.consumption_expiry_revocation_verified,
            certification.readonly_scope_verified,
            certification.audit_verified,
            certification.zero_consumed_reserved_network_verified,
        )):
            raise ResearchRealProviderNetworkExecutionGateError("H37 certification invariants incomplete")
        if (
            certification.boundary_design_id != design.boundary_design_id
            or certification.authorization_id != design.authorization_id
            or certification.authorization_id != authorization.authorization_id
            or certification.injection_id != design.injection_id
            or certification.injection_id != authorization.injection_id
            or certification.injection_id != injected.injection_id
            or certification.transport_object_id != design.transport_object_id
            or certification.transport_object_id != authorization.transport_object_id
            or certification.transport_object_id != injected.transport_object_id
            or certification.transport_identity_id != design.transport_identity_id
            or certification.transport_identity_id != authorization.transport_identity_id
            or certification.transport_identity_id != injected.transport_identity_id
        ):
            raise ResearchRealProviderNetworkExecutionGateError("H37/H36/H34/H30 lineage mismatch")
        if design.state != "designed-authorization-unconsumed-request-unreserved-network-disabled":
            raise ResearchRealProviderNetworkExecutionGateError("H36 boundary not reservable")
        if design.consumption_limit != 1 or design.authorization_consumed or design.request_reserved:
            raise ResearchRealProviderNetworkExecutionGateError("H36 exactly-once boundary already consumed or reserved")
        if not authorization.authorization_issued or authorization.authorization_consumed:
            raise ResearchRealProviderNetworkExecutionGateError("issued unconsumed authorization required")
        if authorization.revoked or not authorization.revocable:
            raise ResearchRealProviderNetworkExecutionGateError("active revocable authorization required")
        if injected.revoked or not injected.revocable:
            raise ResearchRealProviderNetworkExecutionGateError("active revocable injected object required")
        now = self._now()
        try:
            expires_at = datetime.fromisoformat(authorization.expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError) as exc:
            raise ResearchRealProviderNetworkExecutionGateError("invalid authorization expiry") from exc
        if now >= expires_at:
            raise ResearchRealProviderNetworkExecutionGateError("authorization expired")
        if design.authorization_expires_at != authorization.expires_at:
            raise ResearchRealProviderNetworkExecutionGateError("authorization expiry mismatch")

        parsed = urlparse(design.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderNetworkExecutionGateError("unsafe endpoint")
        if design.allowed_method != authorization.allowed_method or design.allowed_method != injected.allowed_method or design.allowed_method != "GET":
            raise ResearchRealProviderNetworkExecutionGateError("H38 remains read-only GET only")
        scope_match = (
            design.operator_id == authorization.operator_id == injected.operator_id
            and design.provider_id == authorization.provider_id == injected.provider_id
            and design.capability == authorization.capability == injected.capability
            and design.endpoint == authorization.endpoint == injected.endpoint
            and design.request_budget == authorization.request_budget == injected.request_budget
            and design.requests_used == authorization.requests_used == injected.requests_used == 0
            and design.timeout_seconds == authorization.timeout_seconds == injected.timeout_seconds
            and design.max_response_bytes == authorization.max_response_bytes == injected.max_response_bytes
            and design.transport_ref == authorization.transport_ref == injected.transport_ref
        )
        if not scope_match:
            raise ResearchRealProviderNetworkExecutionGateError("read-only execution scope mismatch")
        if not 1 <= design.request_budget <= 10:
            raise ResearchRealProviderNetworkExecutionGateError("bounded request budget required")
        if not 1 <= design.timeout_seconds <= 30:
            raise ResearchRealProviderNetworkExecutionGateError("timeout must be 1..30 seconds")
        if not 1 <= design.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderNetworkExecutionGateError("max response bytes must be 1..1048576")
        if any((
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
        )):
            raise ResearchRealProviderNetworkExecutionGateError("H38 requires zero network/credential/write state")

        reservation_id = "research-real-network-execution-reservation-" + self._hash({
            "h37": certification.certification_id,
            "boundary": design.boundary_design_id,
            "authorization": authorization.authorization_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
        })[:24]
        values = (
            reservation_id,
            certification.certification_id,
            design.boundary_design_id,
            authorization.authorization_id,
            injected.injection_id,
            injected.transport_object_id,
            injected.transport_identity_id,
            design.operator_id,
            design.provider_id,
            design.capability,
            design.endpoint,
            design.allowed_method,
            design.request_budget,
            0,
            design.timeout_seconds,
            design.max_response_bytes,
            design.transport_ref,
            authorization.expires_at,
            "authorization-consumed-request-reserved-network-disabled",
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            now.isoformat(),
        )
        try:
            with self._connect() as c:
                c.execute(
                    "INSERT INTO research_real_provider_network_execution_reservations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_network_execution_reservations WHERE reservation_id=?",
                    (reservation_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ResearchRealProviderNetworkExecutionGateError("authorization already consumed or request already reserved") from exc
        return self._from_row(row)

    def revoke(self, reservation_id: str) -> ResearchRealProviderNetworkExecutionReservation:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_network_execution_reservations WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if row is None:
                raise ResearchRealProviderNetworkExecutionGateError("reservation not found")
            if not bool(row["revoked"]):
                c.execute(
                    "UPDATE research_real_provider_network_execution_reservations SET revoked=1, state=? WHERE reservation_id=?",
                    ("reservation-revoked-network-disabled", reservation_id),
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_network_execution_reservations WHERE reservation_id=?",
                    (reservation_id,),
                ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_consumed",
            "request_reserved",
            "revocable",
            "revoked",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderNetworkExecutionReservation(**data)
