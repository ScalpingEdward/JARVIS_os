from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_canary_execution_boundary_design_v21_624 import (
    ResearchRealProviderCanaryExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderCanaryActivationToken,
)


@dataclass(frozen=True)
class ResearchRealProviderCanaryExecutionBoundaryCertification:
    certification_id: str
    boundary_id: str
    token_id: str
    status: str
    blockers: tuple[str, ...]
    token_binding_verified: bool
    one_time_consumption_verified: bool
    endpoint_capability_budget_verified: bool
    audit_safety_verified: bool
    zero_transport_verified: bool
    certified_at: str


class ResearchRealProviderCanaryExecutionBoundaryCertifier:
    """H17 certifies the H16 design only; it cannot consume H15 tokens or execute provider traffic."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_canary_execution_boundary_certifications(
                certification_id TEXT PRIMARY KEY,
                boundary_id TEXT NOT NULL UNIQUE,
                token_id TEXT NOT NULL,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                certified_at TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def certify(
        self,
        boundary: ResearchRealProviderCanaryExecutionBoundaryDesign,
        token: ResearchRealProviderCanaryActivationToken,
        *,
        expected_operator_id: str,
        expected_provider_id: str,
        expected_capability: str,
        allowed_endpoints: tuple[str, ...],
    ) -> ResearchRealProviderCanaryExecutionBoundaryCertification:
        blockers: list[str] = []

        token_binding = (
            boundary.token_id == token.token_id
            and boundary.operator_id == token.operator_id == expected_operator_id
            and boundary.provider_id == token.provider_id == expected_provider_id
            and boundary.capability == token.capability == expected_capability
            and boundary.endpoint == token.endpoint
            and boundary.endpoint in allowed_endpoints
            and boundary.session_request_budget == token.request_budget
        )
        if not token_binding:
            blockers.append("token-or-identity-binding-mismatch")

        one_time_consumption = (
            boundary.token_consumption_limit == 1
            and boundary.consumption_semantics
            == "consume-token-exactly-once-to-open-one-bounded-session"
        )
        if not one_time_consumption:
            blockers.append("one-time-consumption-semantics-invalid")

        parsed = urlparse(boundary.endpoint)
        endpoint_capability_budget = (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
            and boundary.endpoint_enforcement == "exact-token-endpoint-only"
            and boundary.capability_enforcement == "exact-token-capability-only"
            and boundary.budget_enforcement
            == "fail-closed-counter-not-exceed-session-request-budget"
            and isinstance(boundary.session_request_budget, int)
            and 1 <= boundary.session_request_budget <= 10
        )
        if not endpoint_capability_budget:
            blockers.append("endpoint-capability-or-budget-enforcement-invalid")

        audit_safety = (
            boundary.audit_semantics
            == "append-only-metadata-status-request-hash-response-hash-no-raw-secrets"
            and not boundary.audit_request_body_persisted
            and not boundary.audit_raw_credential_persisted
        )
        if not audit_safety:
            blockers.append("audit-safety-invariants-invalid")

        zero_transport = not any(
            (
                boundary.transport_implementation_present,
                boundary.credential_resolution_enabled,
                boundary.provider_write_enabled,
                boundary.production_transport_enabled,
                token.network_execution_enabled,
                token.credential_resolution_enabled,
                token.provider_write_enabled,
                token.production_transport_enabled,
            )
        )
        if not zero_transport:
            blockers.append("transport-credential-resolution-or-write-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-canary-boundary-cert-" + self._hash(
            {
                "boundary": boundary.boundary_id,
                "token": token.token_id,
                "operator": expected_operator_id,
                "provider": expected_provider_id,
                "capability": expected_capability,
                "endpoints": allowed_endpoints,
            }
        )[:24]
        evidence = {
            "token_binding_verified": token_binding,
            "one_time_consumption_verified": one_time_consumption,
            "endpoint_capability_budget_verified": endpoint_capability_budget,
            "audit_safety_verified": audit_safety,
            "zero_transport_verified": zero_transport,
            "token_consumed": False,
            "real_provider_calls_made": 0,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_canary_execution_boundary_certifications VALUES (?,?,?,?,?,?,?)",
                (
                    certification_id,
                    boundary.boundary_id,
                    token.token_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderCanaryExecutionBoundaryCertification(
            certification_id=certification_id,
            boundary_id=boundary.boundary_id,
            token_id=token.token_id,
            status=status,
            blockers=blockers_tuple,
            token_binding_verified=token_binding,
            one_time_consumption_verified=one_time_consumption,
            endpoint_capability_budget_verified=endpoint_capability_budget,
            audit_safety_verified=audit_safety,
            zero_transport_verified=zero_transport,
            certified_at=certified_at,
        )
