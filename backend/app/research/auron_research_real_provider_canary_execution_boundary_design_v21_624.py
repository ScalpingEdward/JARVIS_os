from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderCanaryActivationToken,
)


class ResearchRealProviderCanaryExecutionBoundaryDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderCanaryExecutionBoundaryDesign:
    boundary_id: str
    token_id: str
    operator_id: str
    provider_id: str
    capability: str
    endpoint: str
    token_consumption_limit: int
    session_request_budget: int
    consumption_semantics: str
    endpoint_enforcement: str
    capability_enforcement: str
    budget_enforcement: str
    audit_semantics: str
    audit_request_body_persisted: bool
    audit_raw_credential_persisted: bool
    transport_implementation_present: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str
    expires_at: str


class ResearchRealProviderCanaryExecutionBoundaryDesignRegistry:
    """H16 persists execution-boundary semantics only; it never consumes a token or performs provider I/O."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_canary_execution_boundary_designs(
                boundary_id TEXT PRIMARY KEY,
                token_id TEXT NOT NULL UNIQUE,
                operator_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                token_consumption_limit INTEGER NOT NULL,
                session_request_budget INTEGER NOT NULL,
                consumption_semantics TEXT NOT NULL,
                endpoint_enforcement TEXT NOT NULL,
                capability_enforcement TEXT NOT NULL,
                budget_enforcement TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                audit_request_body_persisted INTEGER NOT NULL,
                audit_raw_credential_persisted INTEGER NOT NULL,
                transport_implementation_present INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash(value):
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _parse_time(value: str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "token expiry must be timezone-aware"
            )
        return dt.astimezone(timezone.utc)

    def register(
        self,
        token: ResearchRealProviderCanaryActivationToken,
        *,
        operator_id: str,
    ) -> ResearchRealProviderCanaryExecutionBoundaryDesign:
        now = self._now()
        expires_at = self._parse_time(token.expires_at)

        if token.state != "armed-not-executable":
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "H15 token must be armed-not-executable"
            )
        if token.operator_id != operator_id:
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "operator mismatch"
            )
        if expires_at <= now:
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "H15 token expired"
            )
        if not token.provider_id or not token.capability or not token.endpoint:
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "provider, capability and endpoint must be pinned"
            )
        if not token.endpoint.lower().startswith("https://"):
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "endpoint must remain HTTPS"
            )
        if not isinstance(token.request_budget, int) or not 1 <= token.request_budget <= 10:
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "session request budget must be 1..10"
            )
        if any(
            (
                token.network_execution_enabled,
                token.credential_resolution_enabled,
                token.provider_write_enabled,
                token.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderCanaryExecutionBoundaryDesignError(
                "H16 requires a zero-transport H15 token"
            )

        boundary_id = "research-real-canary-boundary-" + self._hash(
            {
                "token": token.token_id,
                "operator": operator_id,
                "provider": token.provider_id,
                "capability": token.capability,
                "endpoint": token.endpoint,
                "budget": token.request_budget,
            }
        )[:24]

        values = (
            boundary_id,
            token.token_id,
            operator_id,
            token.provider_id,
            token.capability,
            token.endpoint,
            1,
            token.request_budget,
            "consume-token-exactly-once-to-open-one-bounded-session",
            "exact-token-endpoint-only",
            "exact-token-capability-only",
            "fail-closed-counter-not-exceed-session-request-budget",
            "append-only-metadata-status-request-hash-response-hash-no-raw-secrets",
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
                "INSERT OR IGNORE INTO research_real_provider_canary_execution_boundary_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_canary_execution_boundary_designs WHERE token_id=?",
                (token.token_id,),
            ).fetchone()
        return self._from_row(row)

    def get(self, boundary_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_canary_execution_boundary_designs WHERE boundary_id=?",
                (boundary_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "audit_request_body_persisted",
            "audit_raw_credential_persisted",
            "transport_implementation_present",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderCanaryExecutionBoundaryDesign(**data)
