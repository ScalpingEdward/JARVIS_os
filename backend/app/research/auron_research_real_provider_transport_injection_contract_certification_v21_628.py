from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import (
    ResearchRealProviderCanaryExecutionSession,
)
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import (
    ResearchRealProviderTransportInjectionContract,
)


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionContractCertification:
    certification_id: str
    contract_id: str
    session_id: str
    status: str
    blockers: tuple[str, ...]
    session_binding_verified: bool
    interface_semantics_verified: bool
    endpoint_capability_verified: bool
    budget_sequence_verified: bool
    timeout_response_bounds_verified: bool
    zero_transport_verified: bool
    certified_at: str


class ResearchRealProviderTransportInjectionContractCertifier:
    """H20 certifies H19 contract structure only; it never injects or invokes transport."""

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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_contract_certifications(
                certification_id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
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
        contract: ResearchRealProviderTransportInjectionContract,
        session: ResearchRealProviderCanaryExecutionSession,
    ) -> ResearchRealProviderTransportInjectionContractCertification:
        blockers: list[str] = []

        session_binding = (
            contract.session_id == session.session_id
            and contract.provider_id == session.provider_id
            and contract.capability == session.capability
            and contract.endpoint == session.endpoint
            and contract.request_budget == session.request_budget
            and session.state == "token-consumed-session-open-transport-disabled"
            and session.requests_used == 0
        )
        if not session_binding:
            blockers.append("session-or-provider-contract-binding-mismatch")

        interface_semantics = (
            contract.state == "defined-not-injected"
            and contract.transport_interface_defined
            and contract.allowed_method == "GET"
            and contract.exact_endpoint_required
            and contract.exact_capability_required
            and contract.fail_closed_budget_required
        )
        if not interface_semantics:
            blockers.append("transport-interface-semantics-invalid")

        parsed = urlparse(contract.endpoint)
        endpoint_capability = (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and not parsed.username
            and not parsed.password
            and bool(contract.provider_id)
            and bool(contract.capability)
            and contract.endpoint == session.endpoint
            and contract.capability == session.capability
        )
        if not endpoint_capability:
            blockers.append("endpoint-or-capability-safety-invalid")

        budget_sequence = (
            isinstance(contract.request_budget, int)
            and 1 <= contract.request_budget <= 10
            and contract.request_budget == session.request_budget
            and session.requests_used == 0
            and contract.fail_closed_budget_required
        )
        if not budget_sequence:
            blockers.append("request-budget-or-sequence-semantics-invalid")

        timeout_response_bounds = (
            isinstance(contract.timeout_seconds, int)
            and 1 <= contract.timeout_seconds <= 30
            and isinstance(contract.max_response_bytes, int)
            and 1 <= contract.max_response_bytes <= 1_048_576
        )
        if not timeout_response_bounds:
            blockers.append("timeout-or-response-size-bounds-invalid")

        zero_transport = not any(
            (
                contract.concrete_transport_present,
                contract.network_execution_enabled,
                contract.credential_resolution_enabled,
                contract.provider_write_enabled,
                contract.production_transport_enabled,
                session.transport_injected,
                session.network_execution_enabled,
                session.credential_resolution_enabled,
                session.provider_write_enabled,
                session.production_transport_enabled,
            )
        )
        if not zero_transport:
            blockers.append("transport-credential-resolution-or-write-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-contract-cert-" + self._hash(
            {
                "contract": contract.contract_id,
                "session": session.session_id,
                "provider": contract.provider_id,
                "capability": contract.capability,
                "endpoint": contract.endpoint,
                "budget": contract.request_budget,
                "timeout": contract.timeout_seconds,
                "max_response_bytes": contract.max_response_bytes,
            }
        )[:24]
        evidence = {
            "session_binding_verified": session_binding,
            "interface_semantics_verified": interface_semantics,
            "endpoint_capability_verified": endpoint_capability,
            "budget_sequence_verified": budget_sequence,
            "timeout_response_bounds_verified": timeout_response_bounds,
            "zero_transport_verified": zero_transport,
            "transport_injected": False,
            "real_provider_calls_made": 0,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_contract_certifications VALUES (?,?,?,?,?,?,?)",
                (
                    certification_id,
                    contract.contract_id,
                    session.session_id,
                    status,
                    json.dumps(blockers_tuple),
                    json.dumps(evidence, sort_keys=True),
                    certified_at,
                ),
            )

        return ResearchRealProviderTransportInjectionContractCertification(
            certification_id=certification_id,
            contract_id=contract.contract_id,
            session_id=session.session_id,
            status=status,
            blockers=blockers_tuple,
            session_binding_verified=session_binding,
            interface_semantics_verified=interface_semantics,
            endpoint_capability_verified=endpoint_capability,
            budget_sequence_verified=budget_sequence,
            timeout_response_bounds_verified=timeout_response_bounds,
            zero_transport_verified=zero_transport,
            certified_at=certified_at,
        )
