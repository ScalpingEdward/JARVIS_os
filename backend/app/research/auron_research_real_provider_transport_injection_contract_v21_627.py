from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol
from urllib.parse import urlparse

from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import (
    ResearchRealProviderCanaryExecutionSession,
)


class ResearchRealProviderTransportInjectionContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderTransportRequest:
    method: str
    endpoint: str
    capability: str
    request_index: int
    timeout_seconds: int
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class ResearchRealProviderTransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class ResearchRealProviderInjectedTransport(Protocol):
    """H19 interface shape only. Implementations are introduced by later layers."""

    def send(
        self, request: ResearchRealProviderTransportRequest
    ) -> ResearchRealProviderTransportResponse: ...


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionContract:
    contract_id: str
    session_id: str
    provider_id: str
    capability: str
    endpoint: str
    allowed_method: str
    request_budget: int
    timeout_seconds: int
    max_response_bytes: int
    state: str
    exact_endpoint_required: bool
    exact_capability_required: bool
    fail_closed_budget_required: bool
    transport_interface_defined: bool
    concrete_transport_present: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool


class ResearchRealProviderTransportInjectionContractRegistry:
    """H19 defines an injectable transport contract without installing or invoking transport."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_contracts(
                contract_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                provider_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                allowed_method TEXT NOT NULL,
                request_budget INTEGER NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                max_response_bytes INTEGER NOT NULL,
                state TEXT NOT NULL,
                exact_endpoint_required INTEGER NOT NULL,
                exact_capability_required INTEGER NOT NULL,
                fail_closed_budget_required INTEGER NOT NULL,
                transport_interface_defined INTEGER NOT NULL,
                concrete_transport_present INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL
                )"""
            )

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def register(
        self,
        session: ResearchRealProviderCanaryExecutionSession,
        *,
        timeout_seconds: int = 10,
        max_response_bytes: int = 1_048_576,
    ) -> ResearchRealProviderTransportInjectionContract:
        if session.state != "token-consumed-session-open-transport-disabled":
            raise ResearchRealProviderTransportInjectionContractError(
                "H18 session must be open with transport disabled"
            )
        if session.transport_injected or session.network_execution_enabled:
            raise ResearchRealProviderTransportInjectionContractError(
                "H19 requires transport to remain uninjected and network disabled"
            )
        if any(
            (
                session.credential_resolution_enabled,
                session.provider_write_enabled,
                session.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderTransportInjectionContractError(
                "credential resolution, writes and production transport must remain disabled"
            )
        if not session.provider_id or not session.capability or not session.endpoint:
            raise ResearchRealProviderTransportInjectionContractError(
                "session provider contract is incomplete"
            )
        parsed = urlparse(session.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderTransportInjectionContractError("unsafe endpoint")
        if not isinstance(session.request_budget, int) or not 1 <= session.request_budget <= 10:
            raise ResearchRealProviderTransportInjectionContractError(
                "request budget must be 1..10"
            )
        if session.requests_used != 0:
            raise ResearchRealProviderTransportInjectionContractError(
                "H19 contract requires an unused H18 session"
            )
        if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 30:
            raise ResearchRealProviderTransportInjectionContractError(
                "timeout must be 1..30 seconds"
            )
        if not isinstance(max_response_bytes, int) or not 1 <= max_response_bytes <= 1_048_576:
            raise ResearchRealProviderTransportInjectionContractError(
                "max response bytes must be 1..1048576"
            )

        contract_id = "research-real-transport-contract-" + self._hash(
            {
                "session": session.session_id,
                "provider": session.provider_id,
                "capability": session.capability,
                "endpoint": session.endpoint,
                "budget": session.request_budget,
                "timeout": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )[:24]
        values = (
            contract_id,
            session.session_id,
            session.provider_id,
            session.capability,
            session.endpoint,
            "GET",
            session.request_budget,
            timeout_seconds,
            max_response_bytes,
            "defined-not-injected",
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_contracts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_contracts WHERE session_id=?",
                (session.session_id,),
            ).fetchone()
        return self._from_row(row)

    def validate_request(
        self,
        contract: ResearchRealProviderTransportInjectionContract,
        request: ResearchRealProviderTransportRequest,
        *,
        requests_used: int,
    ) -> None:
        """Validate a future request shape only; this method never invokes transport."""
        if contract.state != "defined-not-injected" or contract.concrete_transport_present:
            raise ResearchRealProviderTransportInjectionContractError(
                "transport contract is not in design-only state"
            )
        if request.method != contract.allowed_method:
            raise ResearchRealProviderTransportInjectionContractError("method not allowed")
        if request.endpoint != contract.endpoint:
            raise ResearchRealProviderTransportInjectionContractError("endpoint mismatch")
        if request.capability != contract.capability:
            raise ResearchRealProviderTransportInjectionContractError("capability mismatch")
        if request.timeout_seconds != contract.timeout_seconds:
            raise ResearchRealProviderTransportInjectionContractError("timeout mismatch")
        if request.body not in (None, b""):
            raise ResearchRealProviderTransportInjectionContractError(
                "GET canary request body is forbidden"
            )
        if not isinstance(requests_used, int) or requests_used < 0:
            raise ResearchRealProviderTransportInjectionContractError(
                "requests_used must be a non-negative integer"
            )
        expected_index = requests_used + 1
        if request.request_index != expected_index:
            raise ResearchRealProviderTransportInjectionContractError(
                "request index must be strictly sequential"
            )
        if expected_index > contract.request_budget:
            raise ResearchRealProviderTransportInjectionContractError(
                "request budget exhausted"
            )

    def get(self, contract_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_injection_contracts WHERE contract_id=?",
                (contract_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "exact_endpoint_required",
            "exact_capability_required",
            "fail_closed_budget_required",
            "transport_interface_defined",
            "concrete_transport_present",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderTransportInjectionContract(**data)
