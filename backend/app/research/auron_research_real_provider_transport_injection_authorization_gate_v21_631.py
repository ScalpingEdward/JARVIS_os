from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.research.auron_research_real_provider_transport_injection_activation_design_certification_v21_630 import (
    ResearchRealProviderTransportInjectionActivationDesignCertification,
)
from app.research.auron_research_real_provider_transport_injection_activation_design_v21_629 import (
    ResearchRealProviderTransportInjectionActivationDesign,
)


class ResearchRealProviderTransportInjectionAuthorizationGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionAuthorization:
    authorization_id: str
    activation_design_certification_id: str
    activation_design_id: str
    operator_id: str
    provider_id: str
    capability: str
    endpoint: str
    allowed_method: str
    request_budget: int
    timeout_seconds: int
    max_response_bytes: int
    transport_ref: str
    state: str
    issued_at: str
    expires_at: str
    injection_authorized: bool
    transport_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool


class ResearchRealProviderTransportInjectionAuthorizationGate:
    """H23 emits short-lived authorization only; transport injection and network execution remain absent."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_authorizations(
                authorization_id TEXT PRIMARY KEY,
                activation_design_certification_id TEXT NOT NULL UNIQUE,
                activation_design_id TEXT NOT NULL UNIQUE,
                operator_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                allowed_method TEXT NOT NULL,
                request_budget INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                max_response_bytes INTEGER NOT NULL,
                transport_ref TEXT NOT NULL,
                state TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                injection_authorized INTEGER NOT NULL,
                transport_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL
                )"""
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def authorize(
        self,
        certification: ResearchRealProviderTransportInjectionActivationDesignCertification,
        design: ResearchRealProviderTransportInjectionActivationDesign,
        *,
        operator_id: str,
        operator_reapproved: bool,
        kill_switch_ready: bool,
        rollback_ready: bool,
        ttl_seconds: int = 120,
    ) -> ResearchRealProviderTransportInjectionAuthorization:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "clean H22 certification required"
            )
        if not all(
            (
                certification.exact_binding_verified,
                certification.opaque_reference_verified,
                certification.safety_controls_verified,
                certification.zero_authorization_transport_verified,
            )
        ):
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "H22 certification invariants incomplete"
            )
        if certification.activation_design_id != design.activation_design_id:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "H22/H21 activation design mismatch"
            )
        if design.state != "designed-not-authorized-not-injected":
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "H21 design is not authorizable"
            )
        if design.operator_id != operator_id or not operator_id:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "operator mismatch"
            )
        if not operator_reapproved:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "fresh operator re-approval required"
            )
        if not kill_switch_ready or not rollback_ready:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "kill-switch and rollback readiness required"
            )
        if not all(
            (
                design.read_only_required,
                design.operator_reapproval_required,
                design.kill_switch_required,
                design.rollback_required,
                design.exact_endpoint_required,
                design.exact_capability_required,
                design.fail_closed_budget_required,
            )
        ):
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "mandatory H21 safety controls missing"
            )
        if design.allowed_method != "GET":
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "authorization is read-only GET only"
            )
        if not 1 <= design.request_budget <= 10:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "request budget must be 1..10"
            )
        if not 1 <= design.timeout_seconds <= 30:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "timeout must be 1..30 seconds"
            )
        if not 1 <= design.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "max response bytes must be 1..1048576"
            )
        if not design.transport_ref.startswith("transportref://"):
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "opaque transport reference required"
            )
        if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 300:
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "authorization TTL must be 1..300 seconds"
            )
        if any(
            (
                design.injection_authorized,
                design.transport_injected,
                design.network_execution_enabled,
                design.credential_resolution_enabled,
                design.provider_write_enabled,
                design.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderTransportInjectionAuthorizationGateError(
                "H23 requires zero authorization/transport state before issuance"
            )

        now = self._now()
        expires = now + timedelta(seconds=ttl_seconds)
        authorization_id = "research-real-transport-injection-auth-" + self._hash(
            {
                "h22": certification.certification_id,
                "design": design.activation_design_id,
                "operator": operator_id,
                "transport_ref": design.transport_ref,
            }
        )[:24]
        values = (
            authorization_id,
            certification.certification_id,
            design.activation_design_id,
            operator_id,
            design.provider_id,
            design.capability,
            design.endpoint,
            design.allowed_method,
            design.request_budget,
            design.timeout_seconds,
            design.max_response_bytes,
            design.transport_ref,
            "authorized-not-injected-not-executable",
            now.isoformat(),
            expires.isoformat(),
            1,
            0,
            0,
            0,
            0,
            0,
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_authorizations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_authorizations WHERE activation_design_certification_id=?",
                (certification.certification_id,),
            ).fetchone()
        return self._from_row(row)

    def get(self, authorization_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "injection_authorized",
            "transport_injected",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderTransportInjectionAuthorization(**data)
