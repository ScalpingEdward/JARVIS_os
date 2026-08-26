from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import ResearchRealProviderCanaryExecutionSession
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import ResearchRealProviderTransportInjectionContract
from app.research.auron_research_real_provider_transport_injection_contract_certification_v21_628 import ResearchRealProviderTransportInjectionContractCertification
from app.research.auron_research_real_provider_transport_injection_activation_design_v21_629 import ResearchRealProviderTransportInjectionActivationDesign


@dataclass(frozen=True)
class ResearchRealProviderTransportInjectionActivationDesignCertification:
    certification_id: str
    activation_design_id: str
    status: str
    blockers: tuple[str, ...]
    exact_binding_verified: bool
    opaque_reference_verified: bool
    safety_controls_verified: bool
    zero_authorization_transport_verified: bool
    certified_at: str


class ResearchRealProviderTransportInjectionActivationDesignCertifier:
    """H22 certifies H21 design only; it cannot authorize or inject transport."""

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
            c.execute("""CREATE TABLE IF NOT EXISTS research_real_provider_transport_injection_activation_design_certifications(
                certification_id TEXT PRIMARY KEY,
                activation_design_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                certified_at TEXT NOT NULL
            )""")

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def certify(
        self,
        design: ResearchRealProviderTransportInjectionActivationDesign,
        certification: ResearchRealProviderTransportInjectionContractCertification,
        contract: ResearchRealProviderTransportInjectionContract,
        session: ResearchRealProviderCanaryExecutionSession,
    ) -> ResearchRealProviderTransportInjectionActivationDesignCertification:
        blockers: list[str] = []

        exact_binding = (
            certification.status == "certified"
            and not certification.blockers
            and certification.certification_id == design.certification_id
            and certification.contract_id == contract.contract_id == design.contract_id
            and certification.session_id == session.session_id == contract.session_id == design.session_id
            and design.provider_id == contract.provider_id == session.provider_id
            and design.capability == contract.capability == session.capability
            and design.endpoint == contract.endpoint == session.endpoint
            and design.allowed_method == contract.allowed_method == "GET"
            and design.request_budget == contract.request_budget == session.request_budget
            and design.timeout_seconds == contract.timeout_seconds
            and design.max_response_bytes == contract.max_response_bytes
            and session.state == "token-consumed-session-open-transport-disabled"
            and session.requests_used == 0
        )
        if not exact_binding:
            blockers.append("h21-h20-h19-h18-binding-mismatch")

        parsed = urlparse(design.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            blockers.append("unsafe-endpoint")

        opaque_reference = (
            isinstance(design.transport_ref, str)
            and design.transport_ref.startswith("transportref://")
            and len(design.transport_ref) > len("transportref://")
        )
        if not opaque_reference:
            blockers.append("opaque-transport-reference-invalid")

        safety_controls = (
            design.state == "designed-not-authorized-not-injected"
            and design.read_only_required
            and design.operator_reapproval_required
            and design.kill_switch_required
            and design.rollback_required
            and design.exact_endpoint_required
            and design.exact_capability_required
            and design.fail_closed_budget_required
            and bool(design.operator_id)
            and 1 <= design.request_budget <= 10
            and 1 <= design.timeout_seconds <= 30
            and 1 <= design.max_response_bytes <= 1_048_576
        )
        if not safety_controls:
            blockers.append("mandatory-activation-safety-controls-missing")

        zero_authorization_transport = not any((
            design.injection_authorized,
            design.transport_injected,
            design.network_execution_enabled,
            design.credential_resolution_enabled,
            design.provider_write_enabled,
            design.production_transport_enabled,
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
        ))
        if not zero_authorization_transport:
            blockers.append("authorization-transport-or-write-already-enabled")

        blockers_tuple = tuple(dict.fromkeys(blockers))
        status = "certified" if not blockers_tuple else "blocked"
        certified_at = self._now()
        certification_id = "research-real-transport-activation-design-cert-" + self._hash({
            "activation_design": design.activation_design_id,
            "h20": certification.certification_id,
            "contract": contract.contract_id,
            "session": session.session_id,
        })[:24]
        evidence = {
            "exact_binding_verified": exact_binding,
            "opaque_reference_verified": opaque_reference,
            "safety_controls_verified": safety_controls,
            "zero_authorization_transport_verified": zero_authorization_transport,
            "injection_authorized": False,
            "transport_injected": False,
            "real_provider_calls_made": 0,
            "credential_resolution_performed": False,
            "provider_writes_performed": False,
        }

        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_injection_activation_design_certifications VALUES (?,?,?,?,?,?)",
                (certification_id, design.activation_design_id, status, json.dumps(blockers_tuple), json.dumps(evidence, sort_keys=True), certified_at),
            )

        return ResearchRealProviderTransportInjectionActivationDesignCertification(
            certification_id,
            design.activation_design_id,
            status,
            blockers_tuple,
            exact_binding,
            opaque_reference,
            safety_controls,
            zero_authorization_transport,
            certified_at,
        )
