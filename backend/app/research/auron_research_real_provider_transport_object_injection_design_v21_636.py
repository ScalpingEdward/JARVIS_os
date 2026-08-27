from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.research.auron_research_real_provider_transport_binding_certification_v21_635 import (
    ResearchRealProviderTransportBindingCertification,
)
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)


class ResearchRealProviderTransportObjectInjectionDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderTransportObjectInjectionDesign:
    injection_design_id: str
    binding_certification_id: str
    binding_id: str
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
    transport_object_contract: str
    identity_binding_semantics: str
    injection_semantics: str
    lifecycle_semantics: str
    revocation_semantics: str
    audit_semantics: str
    state: str
    transport_object_present: bool
    transport_object_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ResearchRealProviderTransportObjectInjectionDesignRegistry:
    """H28 defines a separately injectable concrete transport-object contract only.

    It never accepts a real transport object, injects one, resolves credentials, or
    enables provider networking.
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
                """CREATE TABLE IF NOT EXISTS research_real_provider_transport_object_injection_designs(
                injection_design_id TEXT PRIMARY KEY,
                binding_certification_id TEXT NOT NULL UNIQUE,
                binding_id TEXT NOT NULL UNIQUE,
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
                transport_object_contract TEXT NOT NULL,
                identity_binding_semantics TEXT NOT NULL,
                injection_semantics TEXT NOT NULL,
                lifecycle_semantics TEXT NOT NULL,
                revocation_semantics TEXT NOT NULL,
                audit_semantics TEXT NOT NULL,
                state TEXT NOT NULL,
                transport_object_present INTEGER NOT NULL,
                transport_object_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL
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

    def register(
        self,
        certification: ResearchRealProviderTransportBindingCertification,
        bound: ResearchRealProviderBoundTransportIdentity,
    ) -> ResearchRealProviderTransportObjectInjectionDesign:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "clean H27 certification required"
            )
        if not all(
            (
                certification.lineage_binding_verified,
                certification.consumption_identity_verified,
                certification.scope_budget_verified,
                certification.revocation_verified,
                certification.zero_transport_network_verified,
            )
        ):
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "H27 certification invariants incomplete"
            )
        if (
            certification.binding_id != bound.binding_id
            or certification.transport_identity_id != bound.transport_identity_id
        ):
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "H27/H26 transport identity mismatch"
            )
        if not bound.authorization_consumed or not bound.transport_identity_bound:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "consumed authorization and bound identity required"
            )
        if bound.revoked:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "revoked transport identity cannot enter injection design"
            )
        if bound.state != "authorization-consumed-transport-identity-bound-network-disabled":
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "active network-disabled H26 binding required"
            )
        if bound.allowed_method != "GET":
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "H28 remains read-only GET only"
            )
        parsed = urlparse(bound.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ResearchRealProviderTransportObjectInjectionDesignError("unsafe endpoint")
        if not 1 <= bound.request_budget <= 10 or bound.requests_used != 0:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "unused request budget 1..10 required"
            )
        if not 1 <= bound.timeout_seconds <= 30:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "timeout must be 1..30 seconds"
            )
        if not 1 <= bound.max_response_bytes <= 1_048_576:
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "max response bytes must be 1..1048576"
            )
        if (
            not bound.transport_ref.startswith("transportref://")
            or len(bound.transport_ref) <= len("transportref://")
        ):
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "opaque transport reference required"
            )
        if any(
            (
                bound.transport_injected,
                bound.network_execution_enabled,
                bound.credential_resolution_enabled,
                bound.provider_write_enabled,
                bound.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderTransportObjectInjectionDesignError(
                "H28 requires zero concrete transport/network state"
            )

        injection_design_id = "research-real-transport-object-injection-design-" + self._hash(
            {
                "h27": certification.certification_id,
                "binding": bound.binding_id,
                "identity": bound.transport_identity_id,
                "provider": bound.provider_id,
                "capability": bound.capability,
                "endpoint": bound.endpoint,
                "transport_ref": bound.transport_ref,
            }
        )[:24]
        values = (
            injection_design_id,
            certification.certification_id,
            bound.binding_id,
            bound.transport_identity_id,
            bound.operator_id,
            bound.provider_id,
            bound.capability,
            bound.endpoint,
            bound.allowed_method,
            bound.request_budget,
            bound.requests_used,
            bound.timeout_seconds,
            bound.max_response_bytes,
            bound.transport_ref,
            "callable-readonly-transport-object-with-exact-endpoint-capability-budget-timeout-response-bounds",
            "transport-object-must-bind-exactly-to-h27-certified-transport-identity-id",
            "separate-gate-may-attach-one-object-to-one-certified-identity-without-network-execution",
            "injected-object-remains-network-disabled-until-separate-execution-gate",
            "revocation-invalidates-object-before-any-network-execution",
            "metadata-and-hashes-only-no-raw-credentials-request-or-response-bodies",
            "designed-object-absent-not-injected-network-disabled",
            0,
            0,
            0,
            0,
            0,
            0,
            self._now(),
        )
        with self._connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_real_provider_transport_object_injection_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_object_injection_designs WHERE binding_certification_id=?",
                (certification.certification_id,),
            ).fetchone()
        return self._from_row(row)

    def get(self, injection_design_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_transport_object_injection_designs WHERE injection_design_id=?",
                (injection_design_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "transport_object_present",
            "transport_object_injected",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderTransportObjectInjectionDesign(**data)
