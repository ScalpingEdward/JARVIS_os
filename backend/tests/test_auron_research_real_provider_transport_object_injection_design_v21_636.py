from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_636 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_certification_v21_635 import (
    ResearchRealProviderTransportBindingCertification,
)
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesignError,
    ResearchRealProviderTransportObjectInjectionDesignRegistry,
)


def bound_identity():
    now = datetime.now(timezone.utc)
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
        bound_at=now.isoformat(),
        authorization_expires_at=(now + timedelta(minutes=3)).isoformat(),
    )


def certification(bound):
    return ResearchRealProviderTransportBindingCertification(
        certification_id="h27-cert",
        binding_id=bound.binding_id,
        transport_identity_id=bound.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_binding_verified=True,
        consumption_identity_verified=True,
        scope_budget_verified=True,
        revocation_verified=True,
        zero_transport_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h28_registers_design_without_object_or_network(tmp_path):
    b = bound_identity()
    c = certification(b)
    d = ResearchRealProviderTransportObjectInjectionDesignRegistry(
        tmp_path / "h28.db"
    ).register(c, b)

    assert d.binding_id == b.binding_id
    assert d.transport_identity_id == b.transport_identity_id
    assert d.transport_object_present is False
    assert d.transport_object_injected is False
    assert d.network_execution_enabled is False
    assert d.state == "designed-object-absent-not-injected-network-disabled"


def test_h28_rejects_revoked_or_scope_drift(tmp_path):
    b = bound_identity()
    c = certification(b)
    for drifted in (
        replace(b, revoked=True, state="revoked-network-disabled"),
        replace(b, allowed_method="POST"),
        replace(b, requests_used=1),
        replace(b, transport_injected=True),
        replace(b, network_execution_enabled=True),
    ):
        with pytest.raises(ResearchRealProviderTransportObjectInjectionDesignError):
            ResearchRealProviderTransportObjectInjectionDesignRegistry(
                tmp_path / f"{hash(str(drifted))}.db"
            ).register(c, drifted)


def test_h28_rejects_h27_identity_mismatch(tmp_path):
    b = bound_identity()
    c = replace(certification(b), transport_identity_id="other-identity")
    with pytest.raises(
        ResearchRealProviderTransportObjectInjectionDesignError,
        match="identity mismatch",
    ):
        ResearchRealProviderTransportObjectInjectionDesignRegistry(
            tmp_path / "h28.db"
        ).register(c, b)


def test_h28_is_idempotent_per_h27_certification(tmp_path):
    b = bound_identity()
    c = certification(b)
    registry = ResearchRealProviderTransportObjectInjectionDesignRegistry(tmp_path / "h28.db")
    first = registry.register(c, b)
    second = registry.register(c, b)
    assert first.injection_design_id == second.injection_design_id


def test_h28_readiness_advances_to_h29_without_transport_injection():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.636"
    assert r["next_item"] == "H29-research-real-provider-transport-object-injection-design-certification"
    assert r["real_provider_transport_object_injection_designed"] is True
    assert r["real_provider_transport_object_present"] is False
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
