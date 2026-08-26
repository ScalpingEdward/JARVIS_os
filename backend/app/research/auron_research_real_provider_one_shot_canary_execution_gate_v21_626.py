from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_canary_execution_boundary_certification_v21_625 import (
    ResearchRealProviderCanaryExecutionBoundaryCertification,
)
from app.research.auron_research_real_provider_canary_execution_boundary_design_v21_624 import (
    ResearchRealProviderCanaryExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderCanaryActivationToken,
)


class ResearchRealProviderOneShotCanaryExecutionGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderCanaryExecutionSession:
    session_id: str
    certification_id: str
    boundary_id: str
    token_id: str
    operator_id: str
    provider_id: str
    capability: str
    endpoint: str
    request_budget: int
    requests_used: int
    state: str
    opened_at: str
    expires_at: str
    transport_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool


class ResearchRealProviderOneShotCanaryExecutionGate:
    """H18 consumes one H17-certified H15 token exactly once to open one bounded session.

    Concrete provider transport is intentionally absent in H18.
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
                """CREATE TABLE IF NOT EXISTS research_real_provider_canary_execution_sessions(
                session_id TEXT PRIMARY KEY,
                certification_id TEXT NOT NULL UNIQUE,
                boundary_id TEXT NOT NULL UNIQUE,
                token_id TEXT NOT NULL UNIQUE,
                operator_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_budget INTEGER NOT NULL,
                requests_used INTEGER NOT NULL,
                state TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                transport_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL
                )"""
            )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_time(value: str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "token expiry must be timezone-aware"
            )
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def open_session(
        self,
        certification: ResearchRealProviderCanaryExecutionBoundaryCertification,
        boundary: ResearchRealProviderCanaryExecutionBoundaryDesign,
        token: ResearchRealProviderCanaryActivationToken,
        *,
        operator_id: str,
    ) -> ResearchRealProviderCanaryExecutionSession:
        now = self._now()
        expiry = self._parse_time(token.expires_at)

        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "clean H17 certification required"
            )
        if not all(
            (
                certification.token_binding_verified,
                certification.one_time_consumption_verified,
                certification.endpoint_capability_budget_verified,
                certification.audit_safety_verified,
                certification.zero_transport_verified,
            )
        ):
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "H17 certification invariants incomplete"
            )
        if certification.boundary_id != boundary.boundary_id:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "H17 boundary mismatch"
            )
        if certification.token_id != token.token_id or boundary.token_id != token.token_id:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "H15 token binding mismatch"
            )
        if token.state != "armed-not-executable":
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "H15 token is not consumable"
            )
        if expiry <= now:
            raise ResearchRealProviderOneShotCanaryExecutionGateError("H15 token expired")
        if operator_id != token.operator_id or boundary.operator_id != operator_id:
            raise ResearchRealProviderOneShotCanaryExecutionGateError("operator mismatch")
        if not (
            boundary.provider_id == token.provider_id
            and boundary.capability == token.capability
            and boundary.endpoint == token.endpoint
            and boundary.session_request_budget == token.request_budget
        ):
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "certified provider contract mismatch"
            )
        parsed = urlparse(boundary.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderOneShotCanaryExecutionGateError("unsafe endpoint")
        if boundary.token_consumption_limit != 1 or not 1 <= boundary.session_request_budget <= 10:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "one-shot or request-budget invariant invalid"
            )
        if any(
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
        ):
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "transport, credential resolution or write unexpectedly enabled"
            )

        session_id = "research-real-canary-session-" + self._hash(
            {
                "certification": certification.certification_id,
                "boundary": boundary.boundary_id,
                "token": token.token_id,
                "operator": operator_id,
            }
        )[:24]
        values = (
            session_id,
            certification.certification_id,
            boundary.boundary_id,
            token.token_id,
            operator_id,
            token.provider_id,
            token.capability,
            token.endpoint,
            token.request_budget,
            0,
            "token-consumed-session-open-transport-disabled",
            now.isoformat(),
            expiry.isoformat(),
            0,
            0,
            0,
            0,
            0,
        )
        try:
            with self._connect() as c:
                c.execute(
                    "INSERT INTO research_real_provider_canary_execution_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_canary_execution_sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ResearchRealProviderOneShotCanaryExecutionGateError(
                "H15 token already consumed"
            ) from exc
        return self._from_row(row)

    def get(self, session_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_canary_execution_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "transport_injected",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderCanaryExecutionSession(**data)
