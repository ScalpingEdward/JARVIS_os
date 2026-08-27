from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesign,
)
from app.research.auron_research_real_provider_transport_object_injection_design_certification_v21_637 import (
    ResearchRealProviderTransportObjectInjectionDesignCertification,
)


class ResearchRealProviderTransportObjectInjectionGateError(RuntimeError):
    pass


@runtime_checkable
class ReadOnlyTransportObject(Protocol):
    transport_object_id: str
    provider_id: str
    capability: str
    endpoint: str
    allowed_method: str
    request_budget: int
    timeout_seconds: int
    max_response_bytes: int
    transport_ref: str
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool


@dataclass(frozen=True)
class ResearchRealProviderInjectedTransportObject:
    injection_id: str
    design_certification_id: str
    injection_design_id: str
    binding_id: str
    transport_identity_id: str
    transport_object_id: str
    transport_object_fingerprint: str
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
    transport_object_present: bool
    transport_object_injected: bool
    revocable: bool
    revoked: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    injected_at: str


class ResearchRealProviderTransportObjectInjectionGate:
    """H30 attaches one inert read-only transport object to one clean H29-certified identity.

    The object is scope-checked and persisted by metadata fingerprint only. The gate never
    calls the object and never enables network, credential resolution, writes, or production
    transport.
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
                """CREATE TABLE IF NOT EXISTS research_real_provider_injected_transport_objects(
                injection_id TEXT PRIMARY KEY,
                design_certification_id TEXT NOT NULL UNIQUE,
                injection_design_id TEXT NOT NULL UNIQUE,
                binding_id TEXT NOT NULL UNIQUE,
                transport_identity_id TEXT NOT NULL UNIQUE,
                transport_object_id TEXT NOT NULL UNIQUE,
                transport_object_fingerprint TEXT NOT NULL UNIQUE,
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
                transport_object_present INTEGER NOT NULL,
                transport_object_injected INTEGER NOT NULL,
                revocable INTEGER NOT NULL,
                revoked INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                injected_at TEXT NOT NULL
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

    def inject(
        self,
        certification: ResearchRealProviderTransportObjectInjectionDesignCertification,
        design: ResearchRealProviderTransportObjectInjectionDesign,
        bound: ResearchRealProviderBoundTransportIdentity,
        transport_object: ReadOnlyTransportObject,
    ) -> ResearchRealProviderInjectedTransportObject:
        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderTransportObjectInjectionGateError("clean H29 certification required")
        if not all((
            certification.lineage_identity_verified,
            certification.contract_scope_verified,
            certification.lifecycle_revocation_verified,
            certification.audit_verified,
            certification.zero_object_network_verified,
        )):
            raise ResearchRealProviderTransportObjectInjectionGateError("H29 certification invariants incomplete")
        if (
            certification.injection_design_id != design.injection_design_id
            or certification.binding_id != design.binding_id
            or certification.binding_id != bound.binding_id
            or certification.transport_identity_id != design.transport_identity_id
            or certification.transport_identity_id != bound.transport_identity_id
        ):
            raise ResearchRealProviderTransportObjectInjectionGateError("H29/H28/H26 identity mismatch")
        if bound.revoked or not bound.revocable:
            raise ResearchRealProviderTransportObjectInjectionGateError("active revocable H26 binding required")
        if design.state != "designed-object-absent-not-injected-network-disabled":
            raise ResearchRealProviderTransportObjectInjectionGateError("H28 design not injectable")
        if design.transport_object_present or design.transport_object_injected:
            raise ResearchRealProviderTransportObjectInjectionGateError("H28 design already contains object state")
        if not isinstance(transport_object, ReadOnlyTransportObject):
            raise ResearchRealProviderTransportObjectInjectionGateError("transport object contract mismatch")
        if not transport_object.transport_object_id:
            raise ResearchRealProviderTransportObjectInjectionGateError("transport object id required")
        expected = (
            transport_object.provider_id == design.provider_id == bound.provider_id
            and transport_object.capability == design.capability == bound.capability
            and transport_object.endpoint == design.endpoint == bound.endpoint
            and transport_object.allowed_method == design.allowed_method == bound.allowed_method == "GET"
            and transport_object.request_budget == design.request_budget == bound.request_budget
            and transport_object.timeout_seconds == design.timeout_seconds == bound.timeout_seconds
            and transport_object.max_response_bytes == design.max_response_bytes == bound.max_response_bytes
            and transport_object.transport_ref == design.transport_ref == bound.transport_ref
            and design.requests_used == bound.requests_used == 0
        )
        if not expected:
            raise ResearchRealProviderTransportObjectInjectionGateError("transport object scope mismatch")
        if any((
            transport_object.network_execution_enabled,
            transport_object.credential_resolution_enabled,
            transport_object.provider_write_enabled,
            design.network_execution_enabled,
            design.credential_resolution_enabled,
            design.provider_write_enabled,
            design.production_transport_enabled,
            bound.transport_injected,
            bound.network_execution_enabled,
            bound.credential_resolution_enabled,
            bound.provider_write_enabled,
            bound.production_transport_enabled,
        )):
            raise ResearchRealProviderTransportObjectInjectionGateError("H30 requires inert zero-network transport object")

        fingerprint = self._hash({
            "object_id": transport_object.transport_object_id,
            "provider": transport_object.provider_id,
            "capability": transport_object.capability,
            "endpoint": transport_object.endpoint,
            "method": transport_object.allowed_method,
            "budget": transport_object.request_budget,
            "timeout": transport_object.timeout_seconds,
            "max_response_bytes": transport_object.max_response_bytes,
            "transport_ref": transport_object.transport_ref,
        })
        injection_id = "research-real-transport-object-injection-" + self._hash({
            "h29": certification.certification_id,
            "design": design.injection_design_id,
            "binding": bound.binding_id,
            "identity": bound.transport_identity_id,
            "object": transport_object.transport_object_id,
            "fingerprint": fingerprint,
        })[:24]
        values = (
            injection_id,
            certification.certification_id,
            design.injection_design_id,
            bound.binding_id,
            bound.transport_identity_id,
            transport_object.transport_object_id,
            fingerprint,
            design.operator_id,
            design.provider_id,
            design.capability,
            design.endpoint,
            design.allowed_method,
            design.request_budget,
            0,
            design.timeout_seconds,
            design.max_response_bytes,
            design.transport_ref,
            "transport-object-injected-network-disabled",
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            self._now(),
        )
        try:
            with self._connect() as c:
                c.execute(
                    "INSERT INTO research_real_provider_injected_transport_objects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_injected_transport_objects WHERE injection_id=?",
                    (injection_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ResearchRealProviderTransportObjectInjectionGateError("transport object or certified identity already injected") from exc
        return self._from_row(row)

    def revoke(self, injection_id: str) -> ResearchRealProviderInjectedTransportObject:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_injected_transport_objects WHERE injection_id=?",
                (injection_id,),
            ).fetchone()
            if row is None:
                raise ResearchRealProviderTransportObjectInjectionGateError("injection not found")
            if bool(row["revoked"]):
                return self._from_row(row)
            c.execute(
                "UPDATE research_real_provider_injected_transport_objects SET revoked=1, state=? WHERE injection_id=?",
                ("transport-object-revoked-network-disabled", injection_id),
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_injected_transport_objects WHERE injection_id=?",
                (injection_id,),
            ).fetchone()
        return self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "transport_object_present",
            "transport_object_injected",
            "revocable",
            "revoked",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderInjectedTransportObject(**data)
