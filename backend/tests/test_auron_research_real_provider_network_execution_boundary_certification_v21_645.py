from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_645 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_certification_v21_643 import (
    ResearchRealProviderNetworkExecutionAuthorizationCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_certification_v21_645 import (
    ResearchRealProviderNetworkExecutionBoundaryCertifier,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


def injected():
    return ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection", design_certification_id="h29-cert", injection_design_id="h28-design",
        binding_id="h26-binding", transport_identity_id="transport-identity-1", transport_object_id="transport-object-1",
        transport_object_fingerprint="fingerprint-1", operator_id="operator-1", provider_id="research-provider",
        capability="search-readonly", endpoint="https://sandbox.example.test/search", allowed_method="GET",
        request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref="transportref://research-provider/read-only-canary", state="transport-object-injected-network-disabled",
        transport_object_present=True, transport_object_injected=True, revocable=True, revoked=False,
        network_execution_enabled=False, credential_resolution_enabled=False, provider_write_enabled=False,
        production_transport_enabled=False, injected_at=datetime.now(timezone.utc).isoformat(),
    )


def authorization(i):
    now = datetime.now(timezone.utc)
    return ResearchRealProviderNetworkExecutionAuthorization(
        authorization_id="h34-auth", design_certification_id="h33-cert", authorization_design_id="h32-design",
        injection_id=i.injection_id, transport_object_id=i.transport_object_id, transport_identity_id=i.transport_identity_id,
        operator_id=i.operator_id, provider_id=i.provider_id, capability=i.capability, endpoint=i.endpoint,
        allowed_method="GET", request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref=i.transport_ref, state="authorized-not-consumed-network-disabled", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=180)).isoformat(), authorization_issued=True, authorization_consumed=False,
        revocable=True, revoked=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False,
    )


def h35(a, i):
    return ResearchRealProviderNetworkExecutionAuthorizationCertification(
        certification_id="h35-cert", authorization_id=a.authorization_id, authorization_design_id=a.authorization_design_id,
        injection_id=i.injection_id, transport_object_id=i.transport_object_id, transport_identity_id=i.transport_identity_id,
        status="certified", blockers=(), lineage_identity_verified=True, ttl_expiry_verified=True,
        one_shot_scope_verified=True, revocation_verified=True, zero_consumed_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def boundary(a, c, i):
    return ResearchRealProviderNetworkExecutionBoundaryDesign(
        boundary_design_id="h36-boundary", authorization_certification_id=c.certification_id,
        authorization_id=a.authorization_id, injection_id=i.injection_id, transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id, operator_id=i.operator_id, provider_id=i.provider_id,
        capability=i.capability, endpoint=i.endpoint, allowed_method="GET", request_budget=2, requests_used=0,
        timeout_seconds=10, max_response_bytes=1024, transport_ref=i.transport_ref,
        authorization_expires_at=a.expires_at, consumption_limit=1,
        consumption_semantics="exactly-once-consume-one-clean-h35-certified-authorization-before-any-network-call",
        execution_semantics="later-explicit-execution-gate-may-consume-and-attempt-at-most-one-readonly-request",
        expiry_semantics="authorization-must-be-unexpired-at-consumption-and-fails-closed-after-expiry",
        revocation_semantics="authorization-or-transport-revocation-invalidates-boundary-before-consumption",
        audit_semantics="append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
        state="designed-authorization-unconsumed-request-unreserved-network-disabled",
        authorization_consumed=False, request_reserved=False, network_execution_enabled=False,
        credential_resolution_enabled=False, provider_write_enabled=False, production_transport_enabled=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h37_certifies_clean_design(tmp_path):
    i = injected(); a = authorization(i); c = h35(a, i); d = boundary(a, c, i)
    result = ResearchRealProviderNetworkExecutionBoundaryCertifier(tmp_path / "h37.db").certify(d, c, a, i)
    assert result.status == "certified"
    assert result.blockers == ()
    assert result.lineage_identity_verified
    assert result.consumption_expiry_revocation_verified
    assert result.readonly_scope_verified
    assert result.audit_verified
    assert result.zero_consumed_reserved_network_verified


def test_h37_blocks_identity_and_scope_drift(tmp_path):
    i = injected(); a = authorization(i); c = h35(a, i); d = boundary(a, c, i)
    d = replace(d, transport_identity_id="other", allowed_method="POST")
    result = ResearchRealProviderNetworkExecutionBoundaryCertifier(tmp_path / "h37.db").certify(d, c, a, i)
    assert result.status == "blocked"
    assert "h36-h35-h34-h33-h32-h31-h30-lineage-identity-mismatch" in result.blockers
    assert "boundary-readonly-scope-invalid" in result.blockers


def test_h37_blocks_consumed_reserved_or_network_enabled_state(tmp_path):
    i = injected(); a = authorization(i); c = h35(a, i); d = boundary(a, c, i)
    d = replace(d, authorization_consumed=True, request_reserved=True, network_execution_enabled=True)
    result = ResearchRealProviderNetworkExecutionBoundaryCertifier(tmp_path / "h37.db").certify(d, c, a, i)
    assert result.status == "blocked"
    assert "boundary-consumed-reserved-or-network-state-enabled" in result.blockers


def test_h37_blocks_revoked_authorization(tmp_path):
    i = injected(); a = replace(authorization(i), revoked=True, state="revoked-network-disabled")
    c = h35(a, i); d = boundary(a, c, i)
    result = ResearchRealProviderNetworkExecutionBoundaryCertifier(tmp_path / "h37.db").certify(d, c, a, i)
    assert result.status == "blocked"
    assert "boundary-consumption-expiry-or-revocation-semantics-invalid" in result.blockers


def test_h37_readiness_advances_to_h38_without_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.645"
    assert r["next_item"] == "H38-research-real-provider-network-execution-gate"
    assert r["real_provider_network_execution_boundary_certified"] is True
    assert r["real_provider_network_execution_authorization_consumed"] is False
    assert r["real_provider_network_execution_request_reserved"] is False
    assert r["external_provider_network_enabled"] is False
