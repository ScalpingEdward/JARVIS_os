from dataclasses import dataclass, replace
from datetime import datetime, timezone

import pytest

from app.core.auron_integration_readiness_v21_638 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesign,
)
from app.research.auron_research_real_provider_transport_object_injection_design_certification_v21_637 import (
    ResearchRealProviderTransportObjectInjectionDesignCertification,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderTransportObjectInjectionGate,
    ResearchRealProviderTransportObjectInjectionGateError,
)


@dataclass(frozen=True)
class InertTransport:
    transport_object_id: str = "transport-object-1"
    provider_id: str = "research-provider"
    capability: str = "search-readonly"
    endpoint: str = "https://sandbox.example.test/search"
    allowed_method: str = "GET"
    request_budget: int = 2
    timeout_seconds: int = 10
    max_response_bytes: int = 1024
    transport_ref: str = "transportref://research-provider/read-only-canary"
    network_execution_enabled: bool = False
    credential_resolution_enabled: bool = False
    provider_write_enabled: bool = False


def bound():
    return ResearchRealProviderBoundTransportIdentity(
        binding_id="h26-binding",
        certification_id="h25-cert",
        boundary_id="h24-boundary",
        authorization_id="h23-auth",
        operator_id="operator-1",
        provider_id="research-provider",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        allowed_method="GET",
        request_budget=2,
        requests_used=0,
        timeout_seconds=10,
        max_response_bytes=1024,
        transport_ref="transportref://research-provider/read-only-canary",
        transport_identity_id="transport-identity-1",
        state="authorization-consumed-transport-identity-bound-network-disabled",
        authorization_consumed=True,
        transport_identity_bound=True,
        revocable=True,
        revoked=False,
        transport_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        bound_at=datetime.now(timezone.utc).isoformat(),
        authorization_expires_at=datetime.now(timezone.utc).isoformat(),
    )


def design(b):
    return ResearchRealProviderTransportObjectInjectionDesign(
        injection_design_id="h28-design",
        binding_certification_id="h27-cert",
        binding_id=b.binding_id,
        transport_identity_id=b.transport_identity_id,
        operator_id=b.operator_id,
        provider_id=b.provider_id,
        capability=b.capability,
        endpoint=b.endpoint,
        allowed_method=b.allowed_method,
        request_budget=b.request_budget,
        requests_used=0,
        timeout_seconds=b.timeout_seconds,
        max_response_bytes=b.max_response_bytes,
        transport_ref=b.transport_ref,
        transport_object_contract="callable-readonly-transport-object-with-exact-endpoint-capability-budget-timeout-response-bounds",
        identity_binding_semantics="transport-object-must-bind-exactly-to-h27-certified-transport-identity-id",
        injection_semantics="separate-gate-may-attach-one-object-to-one-certified-identity-without-network-execution",
        lifecycle_semantics="injected-object-remains-network-disabled-until-separate-execution-gate",
        revocation_semantics="revocation-invalidates-object-before-any-network-execution",
        audit_semantics="metadata-and-hashes-only-no-raw-credentials-request-or-response-bodies",
        state="designed-object-absent-not-injected-network-disabled",
        transport_object_present=False,
        transport_object_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def certification(b, d):
    return ResearchRealProviderTransportObjectInjectionDesignCertification(
        certification_id="h29-cert",
        injection_design_id=d.injection_design_id,
        binding_certification_id=d.binding_certification_id,
        binding_id=b.binding_id,
        transport_identity_id=b.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_identity_verified=True,
        contract_scope_verified=True,
        lifecycle_revocation_verified=True,
        audit_verified=True,
        zero_object_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h30_injects_exactly_one_inert_object_without_network(tmp_path):
    b = bound()
    d = design(b)
    c = certification(b, d)
    gate = ResearchRealProviderTransportObjectInjectionGate(tmp_path / "h30.db")
    injected = gate.inject(c, d, b, InertTransport())

    assert injected.transport_object_present is True
    assert injected.transport_object_injected is True
    assert injected.requests_used == 0
    assert injected.state == "transport-object-injected-network-disabled"
    assert injected.network_execution_enabled is False
    assert injected.credential_resolution_enabled is False
    assert injected.provider_write_enabled is False


def test_h30_rejects_second_injection_for_same_identity(tmp_path):
    b = bound()
    d = design(b)
    c = certification(b, d)
    gate = ResearchRealProviderTransportObjectInjectionGate(tmp_path / "h30.db")
    gate.inject(c, d, b, InertTransport())
    with pytest.raises(ResearchRealProviderTransportObjectInjectionGateError, match="already injected"):
        gate.inject(c, d, b, InertTransport(transport_object_id="transport-object-2"))


def test_h30_rejects_scope_drift_or_network_enabled_object(tmp_path):
    b = bound()
    d = design(b)
    c = certification(b, d)
    gate = ResearchRealProviderTransportObjectInjectionGate(tmp_path / "h30.db")

    with pytest.raises(ResearchRealProviderTransportObjectInjectionGateError, match="scope mismatch"):
        gate.inject(c, d, b, replace(InertTransport(), request_budget=3))

    with pytest.raises(ResearchRealProviderTransportObjectInjectionGateError, match="zero-network"):
        gate.inject(c, d, b, replace(InertTransport(), network_execution_enabled=True))


def test_h30_revocation_keeps_network_disabled(tmp_path):
    b = bound()
    d = design(b)
    c = certification(b, d)
    gate = ResearchRealProviderTransportObjectInjectionGate(tmp_path / "h30.db")
    injected = gate.inject(c, d, b, InertTransport())
    revoked = gate.revoke(injected.injection_id)

    assert revoked.revoked is True
    assert revoked.state == "transport-object-revoked-network-disabled"
    assert revoked.network_execution_enabled is False


def test_h30_readiness_advances_to_h31_without_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.638"
    assert r["next_item"] == "H31-research-real-provider-transport-object-injection-certification"
    assert r["real_provider_transport_object_present"] is True
    assert r["real_provider_transport_injected"] is True
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
