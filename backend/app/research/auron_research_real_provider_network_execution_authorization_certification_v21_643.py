from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesign,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_certification_v21_641 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionAuthorizationCertification:
    certification_id: str
    authorization_id: str
    authorization_design_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_identity_verified: bool
    ttl_expiry_verified: bool
    one_shot_scope_verified: bool
    revocation_verified: bool
    zero_consumed_network_verified: bool
    certified_at: str


class ResearchRealProviderNetworkExecutionAuthorizationCertifier:
    """H35 certifies H34 authorization state only; it does not consume or execute it."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_authorization_certifications(
                certification_id TEXT PRIMARY KEY,
                authorization_id TEXT NOT NULL UNIQUE,
                authorization_design_id TEXT NOT NULL,
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
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def certify(
        self,
        authorization: ResearchRealProviderNetworkExecutionAuthorization,
        h33: ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
        design: ResearchRealProviderNetworkExecutionAuthorizationDesign,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionAuthorizationCertification:
        blockers: list[str] = []

        lineage_identity = (
            h33.status == "certified"
            and not h33.blockers
            and h33.lineage_identity_verified
            and h33.ttl_one_shot_verified
            and h33.scope_verified
            and h33.approval_controls_verified
            and h33.audit_zero_network_verified
            and authorization.design_certification_id == h33.certification_id
            and authorization.authorization_design_id == h33.authorization_design_id == design.authorization_design_id
            and authorization.injection_id == h33.injection_id == design.injection_id == injected.injection_id
            and authorization.transport_object_id == h33.transport_object_id == design.transport_object_id == injected.transport_object_id
            and authorization.transport_identity_id == h33.transport_identity_id == design.transport_identity_id == injected.transport_identity_id
        )
        if not lineage_identity:
            blockers.append("h34-h33-h32-h31-h30-lineage-identity-mismatch")

        try:
            issued_at = datetime.fromisoformat(authorization.issued_at)
            expires_at = datetime.fromisoformat(authorization.expires_at)
            if issued_at.tzinfo is None:
                issued_at = issued_at.replace(tzinfo=timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            ttl_seconds = int((expires_at - issued_at).total_seconds())
        except (TypeError, ValueError):
            ttl_seconds = -1
            issued_at = expires_at = self._now()

        ttl_expiry = (
            30 <= design.authorization_ttl_seconds <= 300
            and ttl_seconds == design.authorization_ttl_seconds
            and expires_at > issued_at
            and authorization.authorization_issued
        )
        if not ttl_expiry:
            blockers.append("authorization-ttl-or-expiry-invalid")

        parsed = urlparse(authorization.endpoint)
        one_shot_scope = (
            design.authorization_consumption_limit == 1
            and authorization.operator_id == design.operator_id == injected.operator_id
            and authorization.provider_id == design.provider_id == injected.provider_id
            and authorization.capability == design.capability == injected.capability
            and authorization.endpoint == design.endpoint == injected.endpoint
            and authorization.allowed_method == design.allowed_method == injected.allowed_method == "GET"
            and authorization.request_budget == design.request_budget == injected.request_budget
            and authorization.requests_used == design.requests_used == injected.requests_used == 0
            and authorization.timeout_seconds == design.timeout_seconds == injected.timeout_seconds
            and authorization.max_response_bytes == design.max_response_bytes == injected.max_response_bytes
            and authorization.transport_ref == design.transport_ref == injected.transport_ref
            and 1 <= authorization.request_budget <= 10
            and 1 <= authorization.timeout_seconds <= 30
            and 1 <= authorization.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not one_shot_scope:
            blockers.append("authorization-one-shot-scope-invalid")

        revocation = (
            authorization.revocable
            and (
                (not authorization.revoked and authorization.state == "authorized-not-consumed-network-disabled")
                or (authorization.revoked and authorization.state == "revoked-network-disabled")
            )
        )
        if not revocation:
            blockers.append("authorization-revocation-state-invalid")

        zero_consumed_network = (
            not authorization.authorization_consumed
            and not any((
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
                design.authorization_issued,
                design.authorization_consumed,
                design.network_execution_enabled,
                design.credential_resolution_enabled,
                design.provider_write_enabled,
                design.production_transport_enabled,
                injected.network_execution_enabled,
                injected.credential_resolution_enabled,
                injected.provider_write_enabled,
                injected.production_transport_enabled,
            ))
        )
        if not zero_consumed_network:
            blockers.append("authorization-consumed-or-network-state-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now().isoformat()
        certification_id = "research-real-network-execution-auth-cert-" + self._hash({
            "authorization": authorization.authorization_id,
            "h33": h33.certification_id,
            "design": design.authorization_design_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
            "expires_at": authorization.expires_at,
        })[:24]
        evidence = {
            "lineage_identity_verified": lineage_identity,
            "ttl_expiry_verified": ttl_expiry,
            "one_shot_scope_verified": one_shot_scope,
            "revocation_verified": revocation,
            "zero_consumed_network_verified": zero_consumed_network,
            "authorization_issued": authorization.authorization_issued,
            "authorization_consumed": authorization.authorization_consumed,
            "requests_used": authorization.requests_used,
            "network_execution_enabled": authorization.network_execution_enabled,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_authorization_certifications VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    authorization.authorization_id,
                    design.authorization_design_id,
                    injected.injection_id,
                    injected.transport_object_id,
                    injected.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderNetworkExecutionAuthorizationCertification(
            certification_id=certification_id,
            authorization_id=authorization.authorization_id,
            authorization_design_id=design.authorization_design_id,
            injection_id=injected.injection_id,
            transport_object_id=injected.transport_object_id,
            transport_identity_id=injected.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_identity_verified=lineage_identity,
            ttl_expiry_verified=ttl_expiry,
            one_shot_scope_verified=one_shot_scope,
            revocation_verified=revocation,
            zero_consumed_network_verified=zero_consumed_network,
            certified_at=certified_at,
        )
