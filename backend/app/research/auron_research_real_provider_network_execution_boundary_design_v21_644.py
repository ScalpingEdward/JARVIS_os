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
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


class ResearchRealProviderNetworkExecutionBoundaryDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionBoundaryDesign:
    boundary_design_id: str
    authorization_certification_id: str
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
    consumption_limit: int
    consumption_semantics: str
    execution_semantics: str
    expiry_semantics: str
    revocation_semantics: str
    audit_semantics: str
    state: str
    authorization_consumed: bool
    request_reserved: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ResearchRealProviderNetworkExecutionBoundaryDesignRegistry:
    """H36 defines the fail-closed boundary for later exactly-once authorization consumption.

    Design-only: it never consumes H34 authorization, reserves a request, resolves credentials,
    or performs provider network traffic.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_boundary_designs(
                boundary_design_id TEXT PRIMARY KEY,
                authorization_certification_id TEXT NOT NULL UNIQUE,
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
                consumption_limit INTEGER NOT NULL,
                consumption_semantics TEXT NOT NULL,
                execution_semantics TEXT NOT NULL,
                expiry_semantics TEXT NOT NULL,
                revocation_semantics TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                state TEXT NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                request_reserved INTEGER NOT NULL,
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
        certification: ResearchRealProviderNetworkExecutionAuthorizationCertification,
        authorization: ResearchRealProviderNetworkExecutionAuthorization,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionBoundaryDesign:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("clean H35 certification required")
        if not all((
            certification.lineage_identity_verified,
            certification.ttl_expiry_verified,
            certification.one_shot_scope_verified,
            certification.revocation_verified,
            certification.zero_consumed_network_verified,
        )):
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("H35 certification invariants incomplete")
        if (
            certification.authorization_id != authorization.authorization_id
            or certification.injection_id != authorization.injection_id
            or certification.injection_id != injected.injection_id
            or certification.transport_object_id != authorization.transport_object_id
            or certification.transport_object_id != injected.transport_object_id
            or certification.transport_identity_id != authorization.transport_identity_id
            or certification.transport_identity_id != injected.transport_identity_id
        ):
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("H35/H34/H30 lineage mismatch")
        if not authorization.authorization_issued or authorization.authorization_consumed:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("issued unconsumed authorization required")
        if authorization.revoked or not authorization.revocable:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("active revocable authorization required")
        if authorization.state != "authorized-not-consumed-network-disabled":
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("authorization state not designable")
        if injected.revoked or injected.state != "transport-object-injected-network-disabled":
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("active injected object required")
        parsed = urlparse(authorization.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("unsafe endpoint")
        if authorization.allowed_method != "GET":
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("H36 remains read-only GET only")
        if not 1 <= authorization.request_budget <= 10 or authorization.requests_used != 0:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("unused bounded request budget required")
        if not 1 <= authorization.timeout_seconds <= 30:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("timeout must be 1..30 seconds")
        if not 1 <= authorization.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("max response bytes must be 1..1048576")
        if any((
            authorization.network_execution_enabled,
            authorization.credential_resolution_enabled,
            authorization.provider_write_enabled,
            authorization.production_transport_enabled,
            injected.network_execution_enabled,
            injected.credential_resolution_enabled,
            injected.provider_write_enabled,
            injected.production_transport_enabled,
        )):
            raise ResearchRealProviderNetworkExecutionBoundaryDesignError("H36 requires zero network execution state")

        boundary_design_id = "research-real-network-execution-boundary-design-" + self._hash({
            "h35": certification.certification_id,
            "authorization": authorization.authorization_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
            "expires_at": authorization.expires_at,
        })[:24]
        values = (
            boundary_design_id,
            certification.certification_id,
            authorization.authorization_id,
            injected.injection_id,
            injected.transport_object_id,
            injected.transport_identity_id,
            authorization.operator_id,
            authorization.provider_id,
            authorization.capability,
            authorization.endpoint,
            authorization.allowed_method,
            authorization.request_budget,
            authorization.requests_used,
            authorization.timeout_seconds,
            authorization.max_response_bytes,
            authorization.transport_ref,
            authorization.expires_at,
            1,
            "exactly-once-consume-one-clean-h35-certified-authorization-before-any-network-call",
            "later-explicit-execution-gate-may-consume-and-attempt-at-most-one-readonly-request",
            "authorization-must-be-unexpired-at-consumption-and-fails-closed-after-expiry",
            "authorization-or-transport-revocation-invalidates-boundary-before-consumption",
            "append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
            "designed-authorization-unconsumed-request-unreserved-network-disabled",
            0, 0, 0, 0, 0, 0,
            datetime.now(timezone.utc).isoformat(),
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_boundary_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_network_execution_boundary_designs WHERE authorization_certification_id=?",
                (certification.certification_id,),
            ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_consumed",
            "request_reserved",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderNetworkExecutionBoundaryDesign(**data)
