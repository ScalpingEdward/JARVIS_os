from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesign,
)
from app.research.auron_research_real_provider_transport_injection_boundary_certification_v21_633 import (
    ResearchRealProviderTransportInjectionBoundaryCertification,
)


class ResearchRealProviderTransportBindingGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRealProviderBoundTransportIdentity:
    binding_id: str
    certification_id: str
    boundary_id: str
    authorization_id: str
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
    transport_identity_id: str
    state: str
    authorization_consumed: bool
    transport_identity_bound: bool
    revocable: bool
    revoked: bool
    transport_injected: bool
    network_execution_enabled: bool
    credential_resolution_enabled: bool
    provider_write_enabled: bool
    production_transport_enabled: bool
    bound_at: str
    authorization_expires_at: str


class ResearchRealProviderTransportBindingGate:
    """H26 consumes one H25-certified H23 authorization exactly once to bind identity only.

    No concrete transport object is injected and network execution remains disabled.
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
                """CREATE TABLE IF NOT EXISTS research_real_provider_bound_transport_identities(
                binding_id TEXT PRIMARY KEY,
                certification_id TEXT NOT NULL UNIQUE,
                boundary_id TEXT NOT NULL UNIQUE,
                authorization_id TEXT NOT NULL UNIQUE,
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
                transport_identity_id TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                authorization_consumed INTEGER NOT NULL,
                transport_identity_bound INTEGER NOT NULL,
                revocable INTEGER NOT NULL,
                revoked INTEGER NOT NULL,
                transport_injected INTEGER NOT NULL,
                network_execution_enabled INTEGER NOT NULL,
                credential_resolution_enabled INTEGER NOT NULL,
                provider_write_enabled INTEGER NOT NULL,
                production_transport_enabled INTEGER NOT NULL,
                bound_at TEXT NOT NULL,
                authorization_expires_at TEXT NOT NULL
                )"""
            )

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_time(value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ResearchRealProviderTransportBindingGateError(
                "authorization expiry must be timezone-aware"
            )
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def bind(
        self,
        certification: ResearchRealProviderTransportInjectionBoundaryCertification,
        boundary: ResearchRealProviderTransportInjectionBoundaryDesign,
        authorization: ResearchRealProviderTransportInjectionAuthorization,
        *,
        operator_id: str,
    ) -> ResearchRealProviderBoundTransportIdentity:
        now = self._now()
        expiry = self._parse_time(authorization.expires_at)

        if certification.status != "certified" or certification.blockers:
            raise ResearchRealProviderTransportBindingGateError(
                "clean H25 certification required"
            )
        if not all(
            (
                certification.authorization_binding_verified,
                certification.one_time_consumption_verified,
                certification.transport_identity_lifecycle_revocation_verified,
                certification.budget_audit_verified,
                certification.zero_injection_network_verified,
            )
        ):
            raise ResearchRealProviderTransportBindingGateError(
                "H25 certification invariants incomplete"
            )
        if (
            certification.boundary_id != boundary.boundary_id
            or certification.authorization_id != authorization.authorization_id
            or boundary.authorization_id != authorization.authorization_id
        ):
            raise ResearchRealProviderTransportBindingGateError(
                "H25/H24/H23 binding mismatch"
            )
        if authorization.state != "authorized-not-injected-not-executable":
            raise ResearchRealProviderTransportBindingGateError(
                "H23 authorization is not consumable"
            )
        if not authorization.injection_authorized:
            raise ResearchRealProviderTransportBindingGateError(
                "H23 authorization flag required"
            )
        if expiry <= now:
            raise ResearchRealProviderTransportBindingGateError(
                "H23 authorization expired"
            )
        if operator_id != authorization.operator_id or boundary.operator_id != operator_id:
            raise ResearchRealProviderTransportBindingGateError("operator mismatch")
        if boundary.state != "designed-not-consumed-not-injected":
            raise ResearchRealProviderTransportBindingGateError(
                "H24 boundary is not consumable"
            )
        if boundary.authorization_consumption_limit != 1:
            raise ResearchRealProviderTransportBindingGateError(
                "authorization consumption limit must be exactly one"
            )
        if boundary.authorization_consumed or boundary.transport_identity_bound:
            raise ResearchRealProviderTransportBindingGateError(
                "H24 authorization already consumed or identity already bound"
            )
        if not (
            boundary.provider_id == authorization.provider_id
            and boundary.capability == authorization.capability
            and boundary.endpoint == authorization.endpoint
            and boundary.allowed_method == authorization.allowed_method == "GET"
            and boundary.request_budget == authorization.request_budget
            and boundary.timeout_seconds == authorization.timeout_seconds
            and boundary.max_response_bytes == authorization.max_response_bytes
            and boundary.transport_ref == authorization.transport_ref
        ):
            raise ResearchRealProviderTransportBindingGateError(
                "authorized transport scope mismatch"
            )
        if not 1 <= boundary.request_budget <= 10:
            raise ResearchRealProviderTransportBindingGateError(
                "request budget must be 1..10"
            )
        if any(
            (
                boundary.transport_injected,
                boundary.network_execution_enabled,
                boundary.credential_resolution_enabled,
                boundary.provider_write_enabled,
                boundary.production_transport_enabled,
                authorization.transport_injected,
                authorization.network_execution_enabled,
                authorization.credential_resolution_enabled,
                authorization.provider_write_enabled,
                authorization.production_transport_enabled,
            )
        ):
            raise ResearchRealProviderTransportBindingGateError(
                "H26 requires zero concrete transport/network/credential/write state"
            )

        transport_identity_id = "research-real-transport-identity-" + self._hash(
            {
                "authorization": authorization.authorization_id,
                "transport_ref": boundary.transport_ref,
                "provider": boundary.provider_id,
                "capability": boundary.capability,
                "endpoint": boundary.endpoint,
            }
        )[:24]
        binding_id = "research-real-transport-binding-" + self._hash(
            {
                "certification": certification.certification_id,
                "boundary": boundary.boundary_id,
                "authorization": authorization.authorization_id,
                "identity": transport_identity_id,
            }
        )[:24]
        values = (
            binding_id,
            certification.certification_id,
            boundary.boundary_id,
            authorization.authorization_id,
            operator_id,
            boundary.provider_id,
            boundary.capability,
            boundary.endpoint,
            boundary.allowed_method,
            boundary.request_budget,
            0,
            boundary.timeout_seconds,
            boundary.max_response_bytes,
            boundary.transport_ref,
            transport_identity_id,
            "authorization-consumed-transport-identity-bound-network-disabled",
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            now.isoformat(),
            expiry.isoformat(),
        )
        try:
            with self._connect() as c:
                c.execute(
                    "INSERT INTO research_real_provider_bound_transport_identities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                row = c.execute(
                    "SELECT * FROM research_real_provider_bound_transport_identities WHERE binding_id=?",
                    (binding_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ResearchRealProviderTransportBindingGateError(
                "H23 authorization already consumed"
            ) from exc
        return self._from_row(row)

    def revoke(self, binding_id: str) -> ResearchRealProviderBoundTransportIdentity:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_bound_transport_identities WHERE binding_id=?",
                (binding_id,),
            ).fetchone()
            if row is None:
                raise ResearchRealProviderTransportBindingGateError("binding not found")
            if bool(row["revoked"]):
                return self._from_row(row)
            c.execute(
                "UPDATE research_real_provider_bound_transport_identities SET revoked=1, state=? WHERE binding_id=?",
                ("revoked-network-disabled", binding_id),
            )
            row = c.execute(
                "SELECT * FROM research_real_provider_bound_transport_identities WHERE binding_id=?",
                (binding_id,),
            ).fetchone()
        return self._from_row(row)

    def get(self, binding_id: str):
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM research_real_provider_bound_transport_identities WHERE binding_id=?",
                (binding_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row):
        data = dict(row)
        for key in (
            "authorization_consumed",
            "transport_identity_bound",
            "revocable",
            "revoked",
            "transport_injected",
            "network_execution_enabled",
            "credential_resolution_enabled",
            "provider_write_enabled",
            "production_transport_enabled",
        ):
            data[key] = bool(data[key])
        return ResearchRealProviderBoundTransportIdentity(**data)
