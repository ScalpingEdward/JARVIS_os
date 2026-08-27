from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_635 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_certification_v21_635 import (
    ResearchRealProviderTransportBindingCertifier,
)
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_certification_v21_633 import (
    ResearchRealProviderTransportInjectionBoundaryCertification,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesign,
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


def boundary(a):
    return ResearchRealProviderTransportInjectionBoundaryDesign(
        boundary_id="h24-boundary",
        authorization_id=a.authorization_id,
        operator_id=a.operator_id,
        provider_id=a.provider_id,
        capability=a.capability,
        endpoint=a.endpoint,
        allowed_method=a.allowed_method,
        request_budget=a.request_budget,
        timeout_seconds=a.timeout_seconds,
        max_response_bytes=a.max_response_bytes,
        transport_ref=a.transport_ref,
        authorization_consumption_limit=1,
        authorization_consumption_semantics="consume-authorization-exactly-once-to-bind-one-transport-instance",
        transport_identity_semantics="exact-authorization-transport-ref-instance-only",
        lifecycle_semantics="bind-revocable-transport-instance-before-separate-network-execution-gate",
        revocation_semantics="revocation-invalidates-bound-transport-before-network-execution",
        budget_enforcement="fail-closed-counter-not-exceed-authorized-request-budget",
        audit_semantics="append-only-metadata-status-request-hash-response-hash-no-raw-secrets-or-bodies",
        state="designed-not-consumed-not-injected",
        authorization_consumed=False,
        transport_identity_bound=False,
        transport_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        created_at=datetime.now(timezone.utc).isoformat(),
        authorization_expires_at=a.expires_at,
    )


def h25(a, b):
    return ResearchRealProviderTransportInjectionBoundaryCertification(
        certification_id="h25-cert",
        boundary_id=b.boundary_id,
        authorization_id=a.authorization_id,
        status="certified",
        blockers=(),
        authorization_binding_verified=True,
        one_time_consumption_verified=True,
        transport_identity_lifecycle_revocation_verified=True,
        budget_audit_verified=True,
        zero_injection_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def bound(a, b, c):
    return ResearchRealProviderBoundTransportIdentity(
        binding_id="h26-binding",
        certification_id=c.certification_id,
        boundary_id=b.boundary_id,
        authorization_id=a.authorization_id,
        operator_id=a.operator_id,
        provider_id=a.provider_id,
        capability=a.capability,
        endpoint=a.endpoint,
        allowed_method=a.allowed_method,
        request_budget=a.request_budget,
        requests_used=0,
        timeout_seconds=a.timeout_seconds,
        max_response_bytes=a.max_response_bytes,
        transport_ref=a.transport_ref,
        transport_identity_id="research-real-transport-identity-abc123",
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
        authorization_expires_at=a.expires_at,
    )


def test_h27_certifies_clean_h26_binding_without_transport_execution(tmp_path):
    a = authorization()
    b = boundary(a)
    c = h25(a, b)
    d = bound(a, b, c)
    cert = ResearchRealProviderTransportBindingCertifier(tmp_path / "h27.db").certify(d, c, b, a)

    assert cert.status == "certified"
    assert cert.blockers == ()
    assert cert.lineage_binding_verified is True
    assert cert.consumption_identity_verified is True
    assert cert.scope_budget_verified is True
    assert cert.revocation_verified is True
    assert cert.zero_transport_network_verified is True


def test_h27_blocks_lineage_scope_or_execution_drift(tmp_path):
    a = authorization()
    b = boundary(a)
    c = h25(a, b)
    d = bound(a, b, c)

    cases = (
        replace(d, authorization_id="wrong-auth"),
        replace(d, requests_used=1),
        replace(d, endpoint="http://unsafe.example.test/search"),
        replace(d, network_execution_enabled=True),
    )
    for index, drifted in enumerate(cases):
        cert = ResearchRealProviderTransportBindingCertifier(
            tmp_path / f"h27-{index}.db"
        ).certify(drifted, c, b, a)
        assert cert.status == "blocked"
        assert cert.blockers


def test_h27_accepts_persistently_revoked_identity_only_when_network_disabled(tmp_path):
    a = authorization()
    b = boundary(a)
    c = h25(a, b)
    d = replace(
        bound(a, b, c),
        revoked=True,
        state="revoked-network-disabled",
    )
    cert = ResearchRealProviderTransportBindingCertifier(tmp_path / "revoked.db").certify(d, c, b, a)
    assert cert.status == "certified"
    assert cert.revocation_verified is True
    assert cert.zero_transport_network_verified is True


def test_h27_readiness_advances_to_h28_without_transport_object_injection():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.635"
    assert r["next_item"] == "H28-research-real-provider-transport-object-injection-design"
    assert r["real_provider_transport_binding_certified"] is True
    assert r["real_provider_transport_identity_bound"] is True
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
