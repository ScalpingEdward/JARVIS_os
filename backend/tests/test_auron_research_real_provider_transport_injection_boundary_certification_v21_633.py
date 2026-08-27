from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_633 import get_integration_readiness
from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_certification_v21_633 import (
    ResearchRealProviderTransportInjectionBoundaryCertifier,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesignRegistry,
)


def authorization():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderTransportInjectionAuthorization(
        authorization_id="h23-auth",
        activation_design_certification_id="h22-cert",
        activation_design_id="h21-design",
        operator_id="operator-1",
        provider_id="research-provider",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        allowed_method="GET",
        request_budget=2,
        timeout_seconds=10,
        max_response_bytes=1024,
        transport_ref="transportref://research-provider/read-only-canary",
        state="authorized-not-injected-not-executable",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=3)).isoformat(),
        injection_authorized=True,
        transport_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def boundary(tmp_path, a):
    return ResearchRealProviderTransportInjectionBoundaryDesignRegistry(
        tmp_path / "h24.db"
    ).register(a, operator_id="operator-1")


def certify(tmp_path, b, a):
    return ResearchRealProviderTransportInjectionBoundaryCertifier(
        tmp_path / "h25.db"
    ).certify(b, a)


def test_h25_certifies_clean_h24_boundary_without_consumption_or_injection(tmp_path):
    a = authorization()
    b = boundary(tmp_path, a)
    c = certify(tmp_path, b, a)
    assert c.status == "certified"
    assert c.blockers == ()
    assert c.authorization_binding_verified
    assert c.one_time_consumption_verified
    assert c.transport_identity_lifecycle_revocation_verified
    assert c.budget_audit_verified
    assert c.zero_injection_network_verified


def test_h25_blocks_authorization_binding_mismatch(tmp_path):
    a = authorization()
    b = boundary(tmp_path, a)
    drifted = replace(a, provider_id="other-provider")
    c = certify(tmp_path, b, drifted)
    assert c.status == "blocked"
    assert "h24-h23-authorization-binding-mismatch" in c.blockers


def test_h25_blocks_consumption_identity_budget_audit_and_transport_drift(tmp_path):
    a = authorization()
    b = boundary(tmp_path, a)
    drifted = replace(
        b,
        authorization_consumption_limit=2,
        transport_identity_semantics="anything",
        request_budget=11,
        audit_semantics="raw-body-audit",
        transport_injected=True,
    )
    c = certify(tmp_path, drifted, a)
    assert c.status == "blocked"
    assert "h24-h23-authorization-binding-mismatch" in c.blockers
    assert "authorization-consumption-semantics-invalid" in c.blockers
    assert "transport-identity-lifecycle-or-revocation-invalid" in c.blockers
    assert "budget-or-audit-semantics-invalid" in c.blockers
    assert "transport-network-credential-or-write-enabled" in c.blockers


def test_h25_persistence_is_idempotent_per_boundary(tmp_path):
    a = authorization()
    b = boundary(tmp_path, a)
    certifier = ResearchRealProviderTransportInjectionBoundaryCertifier(tmp_path / "h25.db")
    first = certifier.certify(b, a)
    second = certifier.certify(b, a)
    assert first.certification_id == second.certification_id


def test_h25_readiness_advances_to_h26_without_transport_binding():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.633"
    assert r["next_item"] == "H26-research-real-provider-transport-binding-gate"
    assert r["real_provider_transport_injection_boundary_certified"] is True
    assert r["real_provider_transport_injection_authorization_consumed"] is False
    assert r["real_provider_transport_identity_bound"] is False
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
