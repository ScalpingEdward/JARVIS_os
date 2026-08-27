from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_transport_object_injection_certification_v21_639 import (
    ResearchRealProviderTransportObjectInjectionCertification,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


class ResearchRealProviderNetworkExecutionAuthorizationDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionAuthorizationDesign:
    authorization_design_id: str
    injection_certification_id: str
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
    authorization_ttl_seconds: int
    authorization_consumption_limit: int
    authorization_semantics: str
    reapproval_semantics: str
    kill_switch_semantics: str
    rollback_semantics: str
    audit_semantics: str
    state: str
    authorization_issued: bool
    authorization_consumed: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ResearchRealProviderNetworkExecutionAuthorizationDesignRegistry:
    """H32 defines the authorization artifact required before any H31-certified object may network.

    Design-only: no authorization is issued or consumed and no network/credentials/writes are enabled.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_authorization_designs(
                authorization_design_id TEXT PRIMARY KEY,
                injection_certification_id TEXT NOT NULL UNIQUE,
                injection_id TEXT NOT NULL UNIQUE,
                transport_object_id TEXT NOT NULL UNIQUE,
                transport_identity_id TEXT NOT NULL UNIQUE,
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
                authorization_ttl_seconds INTEGER NOT NULL,
                authorization_consumption_limit INTEGER NOT NULL,
                authorization_semantics TEXT NOT NULL,
                reapproval_semantics TEXT NOT NULL,
                kill_switch_semantics TEXT NOT NULL,
                rollback_semantics TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                state TEXT NOT NULL,
                authorization_issued INTEGER NOT NULL,
                authorization_consumed INTEGER NOT NULL,
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
        certification: ResearchRealProviderTransportObjectInjectionCertification,
        injected: ResearchRealProviderInjectedTransportObject,
        *,
        operator_id: str,
        authorization_ttl_seconds: int = 180,
    ) -> ResearchRealProviderNetworkExecutionAuthorizationDesign:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("clean H31 certification required")
        if not all((
            certification.lineage_verified,
            certification.uniqueness_identity_verified,
            certification.scope_fingerprint_verified,
            certification.revocation_verified,
            certification.zero_network_verified,
        )):
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("H31 certification invariants incomplete")
        if (
            certification.injection_id != injected.injection_id
            or certification.transport_object_id != injected.transport_object_id
            or certification.transport_identity_id != injected.transport_identity_id
        ):
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("H31/H30 object identity mismatch")
        if operator_id != injected.operator_id:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("operator mismatch")
        if injected.revoked or not injected.revocable:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("active revocable injected object required")
        if injected.state != "transport-object-injected-network-disabled":
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("active network-disabled object required")
        parsed = urlparse(injected.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("unsafe endpoint")
        if injected.allowed_method != "GET":
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("H32 remains read-only GET only")
        if not 1 <= injected.request_budget <= 10 or injected.requests_used != 0:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("unused request budget 1..10 required")
        if not 1 <= injected.timeout_seconds <= 30:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("timeout must be 1..30 seconds")
        if not 1 <= injected.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("max response bytes must be 1..1048576")
        if not 30 <= authorization_ttl_seconds <= 300:
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("authorization ttl must be 30..300 seconds")
        if any((
            injected.network_execution_enabled,
            injected.credential_resolution_enabled,
            injected.provider_write_enabled,
            injected.production_transport_enabled,
        )):
            raise ResearchRealProviderNetworkExecutionAuthorizationDesignError("H32 requires zero network/credential/write state")

        authorization_design_id = "research-real-network-execution-auth-design-" + self._hash({
            "h31": certification.certification_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
            "operator": operator_id,
            "provider": injected.provider_id,
            "capability": injected.capability,
            "endpoint": injected.endpoint,
            "transport_ref": injected.transport_ref,
        })[:24]
        values = (
            authorization_design_id,
            certification.certification_id,
            injected.injection_id,
            injected.transport_object_id,
            injected.transport_identity_id,
            operator_id,
            injected.provider_id,
            injected.capability,
            injected.endpoint,
            injected.allowed_method,
            injected.request_budget,
            injected.requests_used,
            injected.timeout_seconds,
            injected.max_response_bytes,
            injected.transport_ref,
            authorization_ttl_seconds,
            1,
            "short-lived-operator-bound-exact-scope-one-shot-network-authorization",
            "fresh-explicit-reapproval-required-before-authorization-issuance",
            "kill-switch-must-be-clear-before-issuance-and-invalidates-authorization",
            "rollback-readiness-required-before-issuance",
            "append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
            "designed-not-issued-not-consumed-network-disabled",
            0, 0, 0, 0, 0, 0,
            datetime.now(timezone.utc).isoformat(),
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_authorization_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_network_execution_authorization_designs WHERE injection_certification_id=?",
                (certification.certification_id,),
            ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_issued",
            "authorization_consumed",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderNetworkExecutionAuthorizationDesign(**data)
