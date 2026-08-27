from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesign,
)


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionBoundaryCertification:
    certification_id: str
    boundary_id: str
    authorization_id: str
    status: str
    blockers: tuple[str, ...]
    authorization_binding_verified: bool
    one_time_consumption_verified: bool
    transport_identity_lifecycle_revocation_verified: bool
    budget_audit_verified: bool
    zero_injection_network_verified: bool
    certified_at: str


class ResearchRealProviderTransportInjectionBoundaryCertifier:
    """H25 certifies H24 design only; it cannot consume authorization or bind/inject transport."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_boundary_certifications(
                certification_id TEXT PRIMARY KEY,
                boundary_id TEXT NOT NULL UNIQUE,
                authorization_id TEXT NOT NULL,
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
        boundary: ResearchRealProviderTransportInjectionBoundaryDesign,
        authorization: ResearchRealProviderTransportInjectionAuthorization,
    ) -> ResearchRealProviderTransportInjectionBoundaryCertification:
        blockers: list[str] = []

        parsed = urlparse(boundary.endpoint)
        authorization_binding = (
            boundary.authorization_id == authorization.authorization_id
            and boundary.operator_id == authorization.operator_id
            and boundary.provider_id == authorization.provider_id
            and boundary.capability == authorization.capability
            and boundary.endpoint == authorization.endpoint
            and boundary.allowed_method == authorization.allowed_method == "GET"
            and boundary.request_budget == authorization.request_budget
            and boundary.timeout_seconds == authorization.timeout_seconds
            and boundary.max_response_bytes == authorization.max_response_bytes
            and boundary.transport_ref == authorization.transport_ref
            and authorization.state == "authorized-not-injected-not-executable"
            and authorization.injection_authorized
            and parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
        )
        if not authorization_binding:
            blockers.append("h24-h23-authorization-binding-mismatch")

        one_time_consumption = (
            boundary.authorization_consumption_limit == 1
            and boundary.authorization_consumption_semantics
            == "consume-authorization-exactly-once-to-bind-one-transport-instance"
            and boundary.state == "designed-not-consumed-not-injected"
            and not boundary.authorization_consumed
        )
        if not one_time_consumption:
            blockers.append("authorization-consumption-semantics-invalid")

        transport_identity_lifecycle_revocation = (
            boundary.transport_identity_semantics
            == "exact-authorization-transport-ref-instance-only"
            and boundary.lifecycle_semantics
            == "bind-revocable-transport-instance-before-separate-network-execution-gate"
            and boundary.revocation_semantics
            == "revocation-invalidates-bound-transport-before-network-execution"
            and boundary.transport_ref.startswith("transportref://")
            and len(boundary.transport_ref) > len("transportref://")
            and not boundary.transport_identity_bound
        )
        if not transport_identity_lifecycle_revocation:
            blockers.append("transport-identity-lifecycle-or-revocation-invalid")

        budget_audit = (
            isinstance(boundary.request_budget, int)
            and 1 <= boundary.request_budget <= 10
            and isinstance(boundary.timeout_seconds, int)
            and 1 <= boundary.timeout_seconds <= 30
            and isinstance(boundary.max_response_bytes, int)
            and 1 <= boundary.max_response_bytes <= 1_048_576
            and boundary.budget_enforcement
            == "fail-closed-counter-not-exceed-authorized-request-budget"
            and boundary.audit_semantics
            == "append-only-metadata-status-request-hash-response-hash-no-raw-secrets-or-bodies"
        )
        if not budget_audit:
            blockers.append("budget-or-audit-semantics-invalid")

        zero_injection_network = not any(
            (
                boundary.transport_injected,
                boundary.network_execution_enabled,
                boundary.credential_resolution_enabled,
                boundary.provider_write_enabled,
                boundary.production_transport_enabled,
                authorization.transport_injected,
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
            )
        )
        if not zero_injection_network:
            blockers.append("transport-network-credential-or-write-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-injection-boundary-cert-" + self._hash(
            {
                "boundary": boundary.boundary_id,
                "authorization": authorization.authorization_id,
                "operator": boundary.operator_id,
                "provider": boundary.provider_id,
                "capability": boundary.capability,
                "endpoint": boundary.endpoint,
                "transport_ref": boundary.transport_ref,
                "budget": boundary.request_budget,
            }
        )[:24]
        evidence = {
            "authorization_binding_verified": authorization_binding,
            "one_time_consumption_verified": one_time_consumption,
            "transport_identity_lifecycle_revocation_verified": transport_identity_lifecycle_revocation,
            "budget_audit_verified": budget_audit,
            "zero_injection_network_verified": zero_injection_network,
            "authorization_consumed": False,
            "transport_identity_bound": False,
            "transport_injected": False,
            "real_provider_calls_made": 0,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_boundary_certifications VALUES (?,?,?,?,?,?,?)",
                (
                    certification_id,
                    boundary.boundary_id,
                    authorization.authorization_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderTransportInjectionBoundaryCertification(
            certification_id=certification_id,
            boundary_id=boundary.boundary_id,
            authorization_id=authorization.authorization_id,
            status=status,
            blockers=blockers_tuple,
            authorization_binding_verified=authorization_binding,
            one_time_consumption_verified=one_time_consumption,
            transport_identity_lifecycle_revocation_verified=transport_identity_lifecycle_revocation,
            budget_audit_verified=budget_audit,
            zero_injection_network_verified=zero_injection_network,
            certified_at=certified_at,
        )
