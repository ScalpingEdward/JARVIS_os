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
from app.research.auron_research_real_provider_transport_object_injection_certification_v21_639 import (
    ResearchRealProviderTransportObjectInjectionCertification,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionAuthorizationDesignCertification:
    certification_id: str
    authorization_design_id: str
    injection_certification_id: str
    injection_id: str
    transport_object_id: str
    transport_identity_id: str
    status: str
    blockers: tuple[str, ...]
    lineage_identity_verified: bool
    ttl_one_shot_verified: bool
    scope_verified: bool
    approval_controls_verified: bool
    audit_zero_network_verified: bool
    certified_at: str


class ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier:
    """H33 certifies H32 design-only authorization semantics; no authorization/network execution."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_authorization_design_certifications(
                certification_id TEXT PRIMARY KEY,
                authorization_design_id TEXT NOT NULL UNIQUE,
                injection_certification_id TEXT NOT NULL,
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
        design: ResearchRealProviderNetworkExecutionAuthorizationDesign,
        h31: ResearchRealProviderTransportObjectInjectionCertification,
        injected: ResearchRealProviderInjectedTransportObject,
    ) -> ResearchRealProviderNetworkExecutionAuthorizationDesignCertification:
        blockers: list[str] = []

        lineage_identity = (
            h31.status == "certified"
            and not h31.blockers
            and h31.lineage_verified
            and h31.uniqueness_identity_verified
            and h31.scope_fingerprint_verified
            and h31.revocation_verified
            and h31.zero_network_verified
            and design.injection_certification_id == h31.certification_id
            and design.injection_id == h31.injection_id == injected.injection_id
            and design.transport_object_id == h31.transport_object_id == injected.transport_object_id
            and design.transport_identity_id == h31.transport_identity_id == injected.transport_identity_id
            and not injected.revoked
            and injected.revocable
            and injected.state == "transport-object-injected-network-disabled"
        )
        if not lineage_identity:
            blockers.append("h32-h31-h30-lineage-identity-mismatch")

        ttl_one_shot = (
            30 <= design.authorization_ttl_seconds <= 300
            and design.authorization_consumption_limit == 1
            and design.authorization_semantics
            == "short-lived-operator-bound-exact-scope-one-shot-network-authorization"
            and design.state == "designed-not-issued-not-consumed-network-disabled"
            and not design.authorization_issued
            and not design.authorization_consumed
        )
        if not ttl_one_shot:
            blockers.append("authorization-ttl-or-one-shot-semantics-invalid")

        parsed = urlparse(design.endpoint)
        scope = (
            design.operator_id == injected.operator_id
            and design.provider_id == injected.provider_id
            and design.capability == injected.capability
            and design.endpoint == injected.endpoint
            and design.allowed_method == injected.allowed_method == "GET"
            and design.request_budget == injected.request_budget
            and design.requests_used == injected.requests_used == 0
            and design.timeout_seconds == injected.timeout_seconds
            and design.max_response_bytes == injected.max_response_bytes
            and design.transport_ref == injected.transport_ref
            and 1 <= design.request_budget <= 10
            and 1 <= design.timeout_seconds <= 30
            and 1 <= design.max_response_bytes <= 1_048_576
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not scope:
            blockers.append("network-authorization-scope-invalid")

        approval_controls = (
            design.reapproval_semantics
            == "fresh-explicit-reapproval-required-before-authorization-issuance"
            and design.kill_switch_semantics
            == "kill-switch-must-be-clear-before-issuance-and-invalidates-authorization"
            and design.rollback_semantics == "rollback-readiness-required-before-issuance"
        )
        if not approval_controls:
            blockers.append("reapproval-kill-switch-or-rollback-semantics-invalid")

        audit_zero_network = (
            design.audit_semantics
            == "append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies"
            and not any((
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
        if not audit_zero_network:
            blockers.append("audit-or-zero-issued-zero-network-state-invalid")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-network-execution-auth-design-cert-" + self._hash({
            "design": design.authorization_design_id,
            "h31": h31.certification_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
        })[:24]
        evidence = {
            "lineage_identity_verified": lineage_identity,
            "ttl_one_shot_verified": ttl_one_shot,
            "scope_verified": scope,
            "approval_controls_verified": approval_controls,
            "audit_zero_network_verified": audit_zero_network,
            "authorization_issued": False,
            "authorization_consumed": False,
            "network_execution_enabled": False,
        }
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_network_execution_authorization_design_certifications VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    certification_id,
                    design.authorization_design_id,
                    h31.certification_id,
                    injected.injection_id,
                    injected.transport_object_id,
                    injected.transport_identity_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderNetworkExecutionAuthorizationDesignCertification(
            certification_id=certification_id,
            authorization_design_id=design.authorization_design_id,
            injection_certification_id=h31.certification_id,
            injection_id=injected.injection_id,
            transport_object_id=injected.transport_object_id,
            transport_identity_id=injected.transport_identity_id,
            status=status,
            blockers=blockers_tuple,
            lineage_identity_verified=lineage_identity,
            ttl_one_shot_verified=ttl_one_shot,
            scope_verified=scope,
            approval_controls_verified=approval_controls,
            audit_zero_network_verified=audit_zero_network,
            certified_at=certified_at,
        )
