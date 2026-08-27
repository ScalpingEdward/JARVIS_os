from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_634 import get_integration_readiness
from app.research.auron_research_real_provider_transport_binding_gate_v21_634 import (
    ResearchRealProviderTransportBindingGate,
    ResearchRealProviderTransportBindingGateError,
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


def certification(a, b):
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


def test_h26_consumes_authorization_once_and_binds_identity_without_network(tmp_path):
    a = authorization()
    b = boundary(a)
    c = certification(a, b)
    gate = ResearchRealProviderTransportBindingGate(tmp_path / "h26.db")
    bound = gate.bind(c, b, a, operator_id="operator-1")

    assert bound.authorization_consumed is True
    assert bound.transport_identity_bound is True
    assert bound.revocable is True
    assert bound.revoked is False
    assert bound.requests_used == 0
    assert bound.state == "authorization-consumed-transport-identity-bound-network-disabled"
    assert bound.transport_injected is False
    assert bound.network_execution_enabled is False
    assert bound.credential_resolution_enabled is False
    assert bound.provider_write_enabled is False


def test_h26_rejects_second_consumption(tmp_path):
    a = authorization()
    b = boundary(a)
    c = certification(a, b)
    gate = ResearchRealProviderTransportBindingGate(tmp_path / "h26.db")
    gate.bind(c, b, a, operator_id="operator-1")
    with pytest.raises(ResearchRealProviderTransportBindingGateError, match="already consumed"):
        gate.bind(c, b, a, operator_id="operator-1")


def test_h26_rejects_expired_or_scope_drift(tmp_path):
    a = authorization()
    b = boundary(a)
    c = certification(a, b)

    expired = replace(a, expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    with pytest.raises(ResearchRealProviderTransportBindingGateError, match="expired"):
        ResearchRealProviderTransportBindingGate(tmp_path / "expired.db").bind(
            c, b, expired, operator_id="operator-1"
        )

    drifted = replace(b, request_budget=3)
    with pytest.raises(ResearchRealProviderTransportBindingGateError, match="scope mismatch"):
        ResearchRealProviderTransportBindingGate(tmp_path / "drift.db").bind(
            c, drifted, a, operator_id="operator-1"
        )


def test_h26_revocation_is_persistent_and_network_stays_disabled(tmp_path):
    a = authorization()
    b = boundary(a)
    c = certification(a, b)
    gate = ResearchRealProviderTransportBindingGate(tmp_path / "h26.db")
    bound = gate.bind(c, b, a, operator_id="operator-1")
    revoked = gate.revoke(bound.binding_id)

    assert revoked.revoked is True
    assert revoked.state == "revoked-network-disabled"
    assert revoked.network_execution_enabled is False
    assert revoked.transport_injected is False


def test_h26_readiness_advances_to_h27_without_network_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.634"
    assert r["next_item"] == "H27-research-real-provider-transport-binding-certification"
    assert r["real_provider_transport_injection_authorization_consumed"] is True
    assert r["real_provider_transport_identity_bound"] is True
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
