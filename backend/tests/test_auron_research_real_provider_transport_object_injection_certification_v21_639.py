from dataclasses import replace
from datetime import datetime, timezone

from app.core.auron_integration_readiness_v21_639 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import ResearchRealProviderBoundTransportIdentity
from app.research.auron_research_real_provider_transport_object_injection_certification_v21_639 import ResearchRealProviderTransportObjectInjectionCertifier
from app.research.auron_research_real_provider_transport_object_injection_design_v21_636 import ResearchRealProviderTransportObjectInjectionDesign
from app.research.auron_research_real_provider_transport_object_injection_design_certification_v21_637 import ResearchRealProviderTransportObjectInjectionDesignCertification
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import ResearchRealProviderInjectedTransportObject


def bound():
    now = datetime.now(timezone.utc).isoformat()
    return ResearchRealProviderBoundTransportIdentity(
        binding_id="h26-binding", certification_id="h25-cert", boundary_id="h24-boundary", authorization_id="h23-auth",
        operator_id="operator-1", provider_id="research-provider", capability="search-readonly",
        endpoint="https://sandbox.example.test/search", allowed_method="GET", request_budget=2, requests_used=0,
        timeout_seconds=10, max_response_bytes=1024, transport_ref="transportref://research-provider/read-only-canary",
        transport_identity_id="transport-identity-1", state="authorization-consumed-transport-identity-bound-network-disabled",
        authorization_consumed=True, transport_identity_bound=True, revocable=True, revoked=False, transport_injected=False,
        network_execution_enabled=False, credential_resolution_enabled=False, provider_write_enabled=False,
        production_transport_enabled=False, bound_at=now, authorization_expires_at=now,
    )


def design(b):
    now = datetime.now(timezone.utc).isoformat()
    return ResearchRealProviderTransportObjectInjectionDesign(
        injection_design_id="h28-design", binding_certification_id="h27-cert", binding_id=b.binding_id,
        transport_identity_id=b.transport_identity_id, operator_id=b.operator_id, provider_id=b.provider_id,
        capability=b.capability, endpoint=b.endpoint, allowed_method="GET", request_budget=2, requests_used=0,
        timeout_seconds=10, max_response_bytes=1024, transport_ref=b.transport_ref,
        transport_object_contract="callable-readonly-transport-object-with-exact-endpoint-capability-budget-timeout-response-bounds",
        identity_binding_semantics="transport-object-must-bind-exactly-to-h27-certified-transport-identity-id",
        injection_semantics="separate-gate-may-attach-one-object-to-one-certified-identity-without-network-execution",
        lifecycle_semantics="injected-object-remains-network-disabled-until-separate-execution-gate",
        revocation_semantics="revocation-invalidates-object-before-any-network-execution",
        audit_semantics="metadata-and-hashes-only-no-raw-credentials-request-or-response-bodies",
        state="designed-object-absent-not-injected-network-disabled", transport_object_present=False,
        transport_object_injected=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False, created_at=now,
    )


def h29(b, d):
    return ResearchRealProviderTransportObjectInjectionDesignCertification(
        certification_id="h29-cert", injection_design_id=d.injection_design_id,
        binding_certification_id=d.binding_certification_id, binding_id=b.binding_id,
        transport_identity_id=b.transport_identity_id, status="certified", blockers=(),
        lineage_identity_verified=True, contract_scope_verified=True, lifecycle_revocation_verified=True,
        audit_verified=True, zero_object_network_verified=True, certified_at=datetime.now(timezone.utc).isoformat(),
    )


def injected(b, d):
    from app.research.auron_research_real_provider_transport_object_injection_certification_v21_639 import ResearchRealProviderTransportObjectInjectionCertifier
    helper = ResearchRealProviderTransportObjectInjectionCertifier._hash
    fingerprint = helper({
        "object_id": "transport-object-1", "provider": b.provider_id, "capability": b.capability,
        "endpoint": b.endpoint, "method": "GET", "budget": 2, "timeout": 10,
        "max_response_bytes": 1024, "transport_ref": b.transport_ref,
    })
    return ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection", design_certification_id="h29-cert", injection_design_id=d.injection_design_id,
        binding_id=b.binding_id, transport_identity_id=b.transport_identity_id, transport_object_id="transport-object-1",
        transport_object_fingerprint=fingerprint, operator_id=b.operator_id, provider_id=b.provider_id,
        capability=b.capability, endpoint=b.endpoint, allowed_method="GET", request_budget=2, requests_used=0,
        timeout_seconds=10, max_response_bytes=1024, transport_ref=b.transport_ref,
        state="transport-object-injected-network-disabled", transport_object_present=True, transport_object_injected=True,
        revocable=True, revoked=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False, injected_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h31_certifies_clean_h30_injection_without_network(tmp_path):
    b = bound(); d = design(b); c = h29(b, d); i = injected(b, d)
    result = ResearchRealProviderTransportObjectInjectionCertifier(tmp_path / "h31.db").certify(i, c, d, b)
    assert result.status == "certified"
    assert result.lineage_verified and result.uniqueness_identity_verified and result.scope_fingerprint_verified
    assert result.revocation_verified and result.zero_network_verified


def test_h31_blocks_fingerprint_or_network_drift(tmp_path):
    b = bound(); d = design(b); c = h29(b, d); i = injected(b, d)
    certifier = ResearchRealProviderTransportObjectInjectionCertifier(tmp_path / "h31.db")
    bad_fp = certifier.certify(replace(i, transport_object_fingerprint="bad"), c, d, b)
    assert bad_fp.status == "blocked"
    assert "transport-object-scope-or-fingerprint-invalid" in bad_fp.blockers

    bad_net = certifier.certify(replace(i, injection_id="h30-injection-2", transport_object_id="transport-object-2", network_execution_enabled=True), c, d, b)
    assert bad_net.status == "blocked"
    assert "network-credential-write-or-production-enabled" in bad_net.blockers


def test_h31_accepts_revoked_but_network_disabled_state(tmp_path):
    b = bound(); d = design(b); c = h29(b, d); i = injected(b, d)
    r = replace(i, state="transport-object-revoked-network-disabled", revoked=True)
    result = ResearchRealProviderTransportObjectInjectionCertifier(tmp_path / "revoked.db").certify(r, c, d, b)
    assert result.status == "certified"
    assert result.revocation_verified is True
    assert result.zero_network_verified is True


def test_h31_readiness_advances_to_h32_without_network_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.639"
    assert r["next_item"] == "H32-research-real-provider-network-execution-authorization-design"
    assert r["real_provider_transport_object_injection_certified"] is True
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
