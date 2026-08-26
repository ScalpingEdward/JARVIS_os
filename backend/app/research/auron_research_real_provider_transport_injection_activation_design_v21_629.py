from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import ResearchRealProviderCanaryExecutionSession
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import ResearchRealProviderTransportInjectionContract
from app.research.auron_research_real_provider_transport_injection_contract_certification_v21_628 import ResearchRealProviderTransportInjectionContractCertification


class ResearchRealProviderTransportInjectionActivationDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionActivationDesign:
    activation_design_id: str
    certification_id: str
    contract_id: str
    session_id: str
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
    read_only_required: bool
    operator_reapproval_required: bool
    kill_switch_required: bool
    rollback_required: bool
    exact_endpoint_required: bool
    exact_capability_required: bool
    fail_closed_budget_required: bool
    injection_authorized: bool
    transport_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ResearchRealProviderTransportInjectionActivationDesignRegistry:
    """H21 persists activation design only; it neither authorizes injection nor invokes transport."""

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
            c.execute("""CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_activation_designs(
                activation_design_id TEXT PRIMARY KEY,
                certification_id TEXT NOT NULL UNIQUE,
                contract_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL UNIQUE,
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
                read_only_required INTEGER NOT NULL,
                operator_reapproval_required INTEGER NOT NULL,
                kill_switch_required INTEGER NOT NULL,
                rollback_required INTEGER NOT NULL,
                exact_endpoint_required INTEGER NOT NULL,
                exact_capability_required INTEGER NOT NULL,
                fail_closed_budget_required INTEGER NOT NULL,
                injection_authorized INTEGER NOT NULL,
                transport_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )""")

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def register(self, certification: ResearchRealProviderTransportInjectionContractCertification, contract: ResearchRealProviderTransportInjectionContract, session: ResearchRealProviderCanaryExecutionSession, *, operator_id: str, transport_ref: str) -> ResearchRealProviderTransportInjectionActivationDesign:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderTransportInjectionActivationDesignError("clean H20 certification required")
        if not all((certification.session_binding_verified, certification.interface_semantics_verified, certification.endpoint_capability_verified, certification.budget_sequence_verified, certification.timeout_response_bounds_verified, certification.zero_transport_verified)):
            raise ResearchRealProviderTransportInjectionActivationDesignError("H20 certification invariants incomplete")
        if certification.contract_id != contract.contract_id or certification.session_id != session.session_id or contract.session_id != session.session_id:
            raise ResearchRealProviderTransportInjectionActivationDesignError("H20/H19/H18 binding mismatch")
        if session.state != "token-consumed-session-open-transport-disabled" or session.requests_used != 0:
            raise ResearchRealProviderTransportInjectionActivationDesignError("unused transport-disabled H18 session required")
        if contract.state != "defined-not-injected" or contract.allowed_method != "GET":
            raise ResearchRealProviderTransportInjectionActivationDesignError("certified GET-only H19 contract required")
        if not (contract.provider_id == session.provider_id and contract.capability == session.capability and contract.endpoint == session.endpoint and contract.request_budget == session.request_budget):
            raise ResearchRealProviderTransportInjectionActivationDesignError("provider contract mismatch")
        if not 1 <= contract.request_budget <= 10 or not 1 <= contract.timeout_seconds <= 30 or not 1 <= contract.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderTransportInjectionActivationDesignError("contract bounds invalid")
        if not operator_id:
            raise ResearchRealProviderTransportInjectionActivationDesignError("operator required")
        if not isinstance(transport_ref, str) or not transport_ref.startswith("transportref://") or len(transport_ref) <= len("transportref://"):
            raise ResearchRealProviderTransportInjectionActivationDesignError("opaque transportref:// reference required")
        if any((contract.concrete_transport_present, contract.network_execution_enabled, contract.credential_resolution_enabled, contract.provider_write_enabled, contract.production_transport_enabled, session.transport_injected, session.network_execution_enabled, session.credential_resolution_enabled, session.provider_write_enabled, session.production_transport_enabled)):
            raise ResearchRealProviderTransportInjectionActivationDesignError("H21 requires zero transport state")

        did = "research-real-transport-activation-design-" + self._hash({"certification": certification.certification_id, "contract": contract.contract_id, "session": session.session_id, "operator": operator_id, "transport_ref": transport_ref})[:24]
        created_at = datetime.now(timezone.utc).isoformat()
        values = (did, certification.certification_id, contract.contract_id, session.session_id, operator_id, contract.provider_id, contract.capability, contract.endpoint, contract.allowed_method, contract.request_budget, contract.timeout_seconds, contract.max_response_bytes, transport_ref, "designed-not-authorized-not-injected", 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, created_at)
        with self._connect() as c:
            c.execute("INSERT OR IGNORE INTO research_real_provider_transport_injection_activation_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            row = c.execute("SELECT * FROM research_real_provider_transport_injection_activation_designs WHERE certification_id=?", (certification.certification_id,)).fetchone()
        return self._from_row(row)

    def get(self, activation_design_id: str):
        with self._connect() as c:
            row = c.execute("SELECT * FROM research_real_provider_transport_injection_activation_designs WHERE activation_design_id=?", (activation_design_id,)).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in ("read_only_required", "operator_reapproval_required", "kill_switch_required", "rollback_required", "exact_endpoint_required", "exact_capability_required", "fail_closed_budget_required", "injection_authorized", "transport_injected", "network_execution_enabled", "credential_resolution_enabled", "provider_write_enabled", "production_transport_enabled"):
            data[key] = bool(data[key])
        return ResearchRealProviderTransportInjectionActivationDesign(**data)
