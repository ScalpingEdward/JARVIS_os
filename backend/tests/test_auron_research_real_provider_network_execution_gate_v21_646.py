from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_646 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_certification_v21_645 import (
    ResearchRealProviderNetworkExecutionBoundaryCertification,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_network_execution_gate_v21_646 import (
    ResearchRealProviderNetworkExecutionGate,
    ResearchRealProviderNetworkExecutionGateError,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


def injected():
    return ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection", design_certification_id="h29-cert", injection_design_id="h28-design",
        binding_id="h26-binding", transport_identity_id="transport-identity-1", transport_object_id="transport-object-1",
        transport_object_fingerprint="fp", operator_id="operator-1", provider_id="research-provider",
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


def design(a, i):
    return ResearchRealProviderNetworkExecutionBoundaryDesign(
        boundary_design_id="h36-boundary", authorization_certification_id="h35-cert", authorization_id=a.authorization_id,
        injection_id=i.injection_id, transport_object_id=i.transport_object_id, transport_identity_id=i.transport_identity_id,
        operator_id=i.operator_id, provider_id=i.provider_id, capability=i.capability, endpoint=i.endpoint, allowed_method="GET",
        request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024, transport_ref=i.transport_ref,
        authorization_expires_at=a.expires_at, consumption_limit=1,
        consumption_semantics="exactly-once-consume-one-clean-h35-certified-authorization-before-any-network-call",
        execution_semantics="later-explicit-execution-gate-may-consume-and-attempt-at-most-one-readonly-request",
        expiry_semantics="authorization-must-be-unexpired-at-consumption-and-fails-closed-after-expiry",
        revocation_semantics="authorization-or-transport-revocation-invalidates-boundary-before-consumption",
        audit_semantics="append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
        state="designed-authorization-unconsumed-request-unreserved-network-disabled", authorization_consumed=False,
        request_reserved=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False, created_at=datetime.now(timezone.utc).isoformat(),
    )


def certification(d, a, i):
    return ResearchRealProviderNetworkExecutionBoundaryCertification(
        certification_id="h37-cert", boundary_design_id=d.boundary_design_id, authorization_certification_id=d.authorization_certification_id,
        authorization_id=a.authorization_id, injection_id=i.injection_id, transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id, status="certified", blockers=(), lineage_identity_verified=True,
        consumption_expiry_revocation_verified=True, readonly_scope_verified=True, audit_verified=True,
        zero_consumed_reserved_network_verified=True, certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h38_consumes_once_and_reserves_without_network(tmp_path):
    i = injected(); a = authorization(i); d = design(a, i); c = certification(d, a, i)
    gate = ResearchRealProviderNetworkExecutionGate(tmp_path / "h38.db")
    r = gate.reserve(c, d, a, i)
    assert r.authorization_consumed is True
    assert r.request_reserved is True
    assert r.reserved_request_count == 1
    assert r.state == "authorization-consumed-request-reserved-network-disabled"
    assert r.network_execution_enabled is False
    assert r.credential_resolution_enabled is False
    assert r.provider_write_enabled is False


def test_h38_rejects_second_reservation(tmp_path):
    i = injected(); a = authorization(i); d = design(a, i); c = certification(d, a, i)
    gate = ResearchRealProviderNetworkExecutionGate(tmp_path / "h38.db")
    gate.reserve(c, d, a, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionGateError, match="already consumed"):
        gate.reserve(c, d, a, i)


def test_h38_rejects_expired_or_revoked_authorization(tmp_path):
    i = injected(); a = authorization(i); d = design(a, i); c = certification(d, a, i)
    expired = replace(a, expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    expired_design = replace(d, authorization_expires_at=expired.expires_at)
    with pytest.raises(ResearchRealProviderNetworkExecutionGateError, match="expired"):
        ResearchRealProviderNetworkExecutionGate(tmp_path / "expired.db").reserve(c, expired_design, expired, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionGateError, match="active revocable authorization"):
        ResearchRealProviderNetworkExecutionGate(tmp_path / "revoked.db").reserve(c, d, replace(a, revoked=True), i)


def test_h38_rejects_scope_or_network_drift(tmp_path):
    i = injected(); a = authorization(i); d = design(a, i); c = certification(d, a, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionGateError, match="scope mismatch"):
        ResearchRealProviderNetworkExecutionGate(tmp_path / "scope.db").reserve(c, replace(d, request_budget=3), a, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionGateError, match="zero network"):
        ResearchRealProviderNetworkExecutionGate(tmp_path / "net.db").reserve(c, d, replace(a, network_execution_enabled=True), i)


def test_h38_revocation_preserves_network_disabled(tmp_path):
    i = injected(); a = authorization(i); d = design(a, i); c = certification(d, a, i)
    gate = ResearchRealProviderNetworkExecutionGate(tmp_path / "h38.db")
    r = gate.reserve(c, d, a, i)
    revoked = gate.revoke(r.reservation_id)
    assert revoked.revoked is True
    assert revoked.state == "reservation-revoked-network-disabled"
    assert revoked.network_execution_enabled is False


def test_h38_readiness_advances_to_h39_without_provider_traffic():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.646"
    assert r["next_item"] == "H39-research-real-provider-network-execution-gate-certification"
    assert r["real_provider_network_execution_authorization_consumed"] is True
    assert r["real_provider_network_execution_request_reserved"] is True
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
