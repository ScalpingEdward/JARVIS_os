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


class ResearchRealProviderTransportInjectionBoundaryDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionBoundaryDesign:
    boundary_id: str
    authorization_id: str
    operator_id: str
    provider_id: str
    capability: str
    endpoint: str
    allowed_method: str
    request_budget: int
    timeout_seconds: int
    max_response_bytes: int
    transport_ref: str
    authorization_consumption_limit: int
    authorization_consumption_semantics: str
    transport_identity_semantics: str
    lifecycle_semantics: str
    revocation_semantics: str
    budget_enforcement: str
    audit_semantics: str
    state: str
    authorization_consumed: bool
    transport_identity_bound: bool
    transport_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str
    authorization_expires_at: str


class ResearchRealProviderTransportInjectionBoundaryDesignRegistry:
    """H24 defines authorization-consumption and transport-binding semantics only.

    It never consumes H23 authorization, injects transport, resolves credentials,
    or executes provider traffic.
    """

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_boundary_designs(
                boundary_id TEXT PRIMARY KEY,
                authorization_id TEXT NOT NULL UNIQUE,
                operator_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                allowed_method TEXT NOT NULL,
                request_budget INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                max_response_bytes INTEGER NOT NULL,
                transport_ref TEXT NOT NULL,
                authorization_consumption_limit INTEGER NOT NULL,
                authorization_consumption_semantics TEXT NOT NULL,
                transport_identity_semantics TEXT NOT NULL,
                lifecycle_semantics TEXT NOT NULL,
                revocation_semantics TEXT NOT NULL,
                budget_enforcement TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                state TEXT NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                transport_identity_bound INTEGER NOT NULL,
                transport_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                authorization_expires_at TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_time(value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "authorization expiry must be timezone-aware"
            )
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def register(
        self,
        authorization: ResearchRealProviderTransportInjectionAuthorization,
        *,
        operator_id: str,
    ) -> ResearchRealProviderTransportInjectionBoundaryDesign:
        now = self._now()
        expires_at = self._parse_time(authorization.expires_at)

        if authorization.state != "authorized-not-injected-not-executable":
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "H23 authorization must be authorized-not-injected-not-executable"
            )
        if not authorization.injection_authorized:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "H23 injection authorization flag required"
            )
        if authorization.operator_id != operator_id or not operator_id:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "operator mismatch"
            )
        if expires_at <= now:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "H23 authorization expired"
            )
        if authorization.allowed_method != "GET":
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "H24 remains read-only GET only"
            )
        parsed = urlparse(authorization.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "unsafe endpoint"
            )
        if not authorization.provider_id or not authorization.capability:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "provider and capability must be pinned"
            )
        if not 1 <= authorization.request_budget <= 10:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "request budget must be 1..10"
            )
        if not 1 <= authorization.timeout_seconds <= 30:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "timeout must be 1..30 seconds"
            )
        if not 1 <= authorization.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "max response bytes must be 1..1048576"
            )
        if (
            not isinstance(authorization.transport_ref, str)
            or not authorization.transport_ref.startswith("transportref://")
            or len(authorization.transport_ref) <= len("transportref://")
        ):
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "opaque transportref:// reference required"
            )
        if any(
            (
                authorization.transport_injected,
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderTransportInjectionBoundaryDesignError(
                "H24 requires zero injected/network/credential/write state"
            )

        boundary_id = "research-real-transport-injection-boundary-" + self._hash(
            {
                "authorization": authorization.authorization_id,
                "operator": operator_id,
                "provider": authorization.provider_id,
                "capability": authorization.capability,
                "endpoint": authorization.endpoint,
                "transport_ref": authorization.transport_ref,
                "budget": authorization.request_budget,
            }
        )[:24]
        values = (
            boundary_id,
            authorization.authorization_id,
            operator_id,
            authorization.provider_id,
            authorization.capability,
            authorization.endpoint,
            authorization.allowed_method,
            authorization.request_budget,
            authorization.timeout_seconds,
            authorization.max_response_bytes,
            authorization.transport_ref,
            1,
            "consume-authorization-exactly-once-to-bind-one-transport-instance",
            "exact-authorization-transport-ref-instance-only",
            "bind-revocable-transport-instance-before-separate-network-execution-gate",
            "revocation-invalidates-bound-transport-before-network-execution",
            "fail-closed-counter-not-exceed-authorized-request-budget",
            "append-only-metadata-status-request-hash-response-hash-no-raw-secrets-or-bodies",
            "designed-not-consumed-not-injected",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            now.isoformat(),
            expires_at.isoformat(),
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_boundary_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_boundary_designs WHERE authorization_id=?",
                (authorization.authorization_id,),
            ).fetchone()
        return self._from_row(row)

    def get(self, boundary_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_boundary_designs WHERE boundary_id=?",
                (boundary_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_consumed",
            "transport_identity_bound",
            "transport_injected",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderTransportInjectionBoundaryDesign(**data)
