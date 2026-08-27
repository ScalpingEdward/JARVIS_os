from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesign,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_certification_v21_641 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


class ResearchRealProviderNetworkExecutionAuthorizationGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderNetworkExecutionAuthorization:
    authorization_id: str
    design_certification_id: str
    authorization_design_id: str
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
    state: str
    issued_at: str
    expires_at: str
    authorization_issued: bool
    authorization_consumed: bool
    revocable: bool
    revoked: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool


class ResearchRealProviderNetworkExecutionAuthorizationGate:
    """H34 issues one short-lived, one-shot authorization but enables no network execution."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS research_real_provider_network_execution_authorizations(
                authorization_id TEXT PRIMARY KEY,
                design_certification_id TEXT NOT NULL UNIQUE,
                authorization_design_id TEXT NOT NULL UNIQUE,
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
                state TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                authorization_issued INTEGER NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                revocable INTEGER NOT NULL,
                revoked INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL
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

    def issue(
        self,
        certification: ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
        design: ResearchRealProviderNetworkExecutionAuthorizationDesign,
        injected: ResearchRealProviderInjectedTransportObject,
        *,
        operator_id: str,
        fresh_reapproval: bool,
        kill_switch_clear: bool,
        rollback_ready: bool,
    ) -> ResearchRealProviderNetworkExecutionAuthorization:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("clean H33 certification required")
        if not all((
            certification.lineage_identity_verified,
            certification.ttl_one_shot_verified,
            certification.scope_verified,
            certification.approval_controls_verified,
            certification.audit_zero_network_verified,
        )):
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("H33 certification invariants incomplete")
        if (
            certification.authorization_design_id != design.authorization_design_id
            or certification.injection_id != design.injection_id
            or certification.injection_id != injected.injection_id
            or certification.transport_object_id != injected.transport_object_id
            or certification.transport_identity_id != injected.transport_identity_id
        ):
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("H33/H32/H30 identity mismatch")
        if operator_id != design.operator_id or operator_id != injected.operator_id:
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("operator mismatch")
        if not (fresh_reapproval and kill_switch_clear and rollback_ready):
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("fresh reapproval, clear kill switch and rollback readiness required")
        if injected.revoked or not injected.revocable or injected.state != "transport-object-injected-network-disabled":
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("active revocable injected object required")
        if design.state != "designed-not-issued-not-consumed-network-disabled":
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("H32 design not issuable")
        if design.authorization_consumption_limit != 1 or not 30 <= design.authorization_ttl_seconds <= 300:
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("invalid one-shot authorization design")
        if design.requests_used != 0 or injected.requests_used != 0:
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("authorization requires zero prior requests")
        if any((
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
        )):
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("H34 requires zero network/credential/write execution state")

        now = self._now()
        expires = now + timedelta(seconds=design.authorization_ttl_seconds)
        authorization_id = "research-real-network-execution-auth-" + self._hash({
            "h33": certification.certification_id,
            "design": design.authorization_design_id,
            "injection": injected.injection_id,
            "object": injected.transport_object_id,
            "identity": injected.transport_identity_id,
            "operator": operator_id,
            "issued_at": now.isoformat(),
        })[:24]
        values = (
            authorization_id,
            certification.certification_id,
            design.authorization_design_id,
            injected.injection_id,
            injected.transport_object_id,
            injected.transport_identity_id,
            operator_id,
            design.provider_id,
            design.capability,
            design.endpoint,
            design.allowed_method,
            design.request_budget,
            0,
            design.timeout_seconds,
            design.max_response_bytes,
            design.transport_ref,
            "authorized-not-consumed-network-disabled",
            now.isoformat(),
            expires.isoformat(),
            1, 0, 1, 0, 0, 0, 0, 0,
        )
        try:
            with self._connect() as c:
                c.execute(
                    "INSERT INTO research_real_provider_network_execution_authorizations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_network_execution_authorizations WHERE authorization_id=?",
                    (authorization_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ResearchRealProviderNetworkExecutionAuthorizationGateError("network execution authorization already issued") from exc
        return self._from_row(row)

    def revoke(self, authorization_id: str) -> ResearchRealProviderNetworkExecutionAuthorization:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_network_execution_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise ResearchRealProviderNetworkExecutionAuthorizationGateError("authorization not found")
            if not bool(row["revoked"]):
                c.execute(
                    "UPDATE research_real_provider_network_execution_authorizations SET revoked=1, state=? WHERE authorization_id=?",
                    ("revoked-network-disabled", authorization_id),
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_network_execution_authorizations WHERE authorization_id=?",
                    (authorization_id,),
                ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_issued",
            "authorization_consumed",
            "revocable",
            "revoked",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderNetworkExecutionAuthorization(**data)
