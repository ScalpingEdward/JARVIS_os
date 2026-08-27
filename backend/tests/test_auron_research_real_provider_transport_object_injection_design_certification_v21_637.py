from dataclasses import replace
from datetime import datetime, timezone

from app.core.auron_integration_readiness_v21_637 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_certification_v21_635 import (
    ResearchRealProviderTransportBindingCertification,
)
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderBoundTransportIdentity,
)
from app.research.auron_research_real_provider_transport_object_injection_design_certification_v21_637 import (
    ResearchRealProviderTransportObjectInjectionDesignCertifier,
)
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import (
    ResearchRealProviderTransportObjectInjectionDesign,
)


def bound_identity():
    now = datetime.now(timezone.utc).isoformat()
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
        transport_identity_id="h26-transport-identity",
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
        bound_at=now,
        authorization_expires_at=now,
    )


def h27(bound):
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


def design(bound, cert):
    return ResearchRealProviderTransportObjectInjectionDesign(
        injection_design_id="h28-design",
        binding_certification_id=cert.certification_id,
        binding_id=bound.binding_id,
        transport_identity_id=bound.transport_identity_id,
        operator_id=bound.operator_id,
        provider_id=bound.provider_id,
        capability=bound.capability,
        endpoint=bound.endpoint,
        allowed_method=bound.allowed_method,
        request_budget=bound.request_budget,
        requests_used=bound.requests_used,
        timeout_seconds=bound.timeout_seconds,
        max_response_bytes=bound.max_response_bytes,
        transport_ref=bound.transport_ref,
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


def test_h29_certifies_h28_without_object_or_network(tmp_path):
    b = bound_identity()
    c = h27(b)
    d = design(b, c)
    result = ResearchRealProviderTransportObjectInjectionDesignCertifier(
        tmp_path / "h29.db"
    ).certify(d, c, b)

    assert result.status == "certified"
    assert result.blockers == ()
    assert result.lineage_identity_verified is True
    assert result.contract_scope_verified is True
    assert result.lifecycle_revocation_verified is True
    assert result.audit_verified is True
    assert result.zero_object_network_verified is True


def test_h29_blocks_identity_or_scope_drift(tmp_path):
    b = bound_identity()
    c = h27(b)
    d = design(b, c)
    certifier = ResearchRealProviderTransportObjectInjectionDesignCertifier(tmp_path / "h29.db")

    drifted = replace(d, transport_identity_id="wrong-identity")
    result = certifier.certify(drifted, c, b)
    assert result.status == "blocked"
    assert "h28-h27-h26-lineage-identity-mismatch" in result.blockers


def test_h29_blocks_present_object_or_network_state(tmp_path):
    b = bound_identity()
    c = h27(b)
    d = design(b, c)
    certifier = ResearchRealProviderTransportObjectInjectionDesignCertifier(tmp_path / "h29.db")

    result = certifier.certify(replace(d, transport_object_present=True), c, b)
    assert result.status == "blocked"
    assert "transport-object-network-credential-or-write-enabled" in result.blockers


def test_h29_readiness_advances_to_h30_without_transport_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.637"
    assert r["next_item"] == "H30-research-real-provider-transport-object-injection-gate"
    assert r["real_provider_transport_object_injection_design_certified"] is True
    assert r["real_provider_transport_object_present"] is False
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
