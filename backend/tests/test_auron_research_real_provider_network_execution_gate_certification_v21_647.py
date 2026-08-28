from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_647 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_certification_v21_645 import (
    ResearchRealProviderNetworkExecutionBoundaryCertification,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesign,
)
from app.research.auron_research_real_provider_network_execution_gate_certification_v21_647 import (
    ResearchRealProviderNetworkExecutionGateCertifier,
)
from app.research.auron_research_real_provider_network_execution_gate_v21_646 import (
    ResearchRealProviderNetworkExecutionReservation,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


def fixtures():
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(seconds=180)).isoformat()
    injected = ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection", design_certification_id="h29-cert", injection_design_id="h28-design",
        binding_id="h26-binding", transport_identity_id="transport-identity-1", transport_object_id="transport-object-1",
        transport_object_fingerprint="fp", operator_id="operator-1", provider_id="research-provider",
        capability="search-readonly", endpoint="https://sandbox.example.test/search", allowed_method="GET",
        request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref="transportref://research-provider/read-only-canary", state="transport-object-injected-network-disabled",
        transport_object_present=True, transport_object_injected=True, revocable=True, revoked=False,
        network_execution_enabled=False, credential_resolution_enabled=False, provider_write_enabled=False,
        production_transport_enabled=False, injected_at=now.isoformat(),
    )
    authorization = ResearchRealProviderNetworkExecutionAuthorization(
        authorization_id="h34-auth", design_certification_id="h33-cert", authorization_design_id="h32-design",
        injection_id=injected.injection_id, transport_object_id=injected.transport_object_id,
        transport_identity_id=injected.transport_identity_id, operator_id=injected.operator_id,
        provider_id=injected.provider_id, capability=injected.capability, endpoint=injected.endpoint,
        allowed_method="GET", request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref=injected.transport_ref, state="authorized-not-consumed-network-disabled", issued_at=now.isoformat(),
        expires_at=expires, authorization_issued=True, authorization_consumed=False, revocable=True, revoked=False,
        network_execution_enabled=False, credential_resolution_enabled=False, provider_write_enabled=False,
        production_transport_enabled=False,
    )
    design = ResearchRealProviderNetworkExecutionBoundaryDesign(
        boundary_design_id="h36-boundary", authorization_certification_id="h35-cert", authorization_id=authorization.authorization_id,
        injection_id=injected.injection_id, transport_object_id=injected.transport_object_id,
        transport_identity_id=injected.transport_identity_id, operator_id=injected.operator_id,
        provider_id=injected.provider_id, capability=injected.capability, endpoint=injected.endpoint, allowed_method="GET",
        request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref=injected.transport_ref, authorization_expires_at=expires, consumption_limit=1,
        consumption_semantics="exactly-once-consume-one-clean-h35-certified-authorization-before-any-network-call",
        execution_semantics="later-explicit-execution-gate-may-consume-and-attempt-at-most-one-readonly-request",
        expiry_semantics="authorization-must-be-unexpired-at-consumption-and-fails-closed-after-expiry",
        revocation_semantics="authorization-or-transport-revocation-invalidates-boundary-before-consumption",
        audit_semantics="append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
        state="designed-authorization-unconsumed-request-unreserved-network-disabled", authorization_consumed=False,
        request_reserved=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False, created_at=now.isoformat(),
    )
    h37 = ResearchRealProviderNetworkExecutionBoundaryCertification(
        certification_id="h37-cert", boundary_design_id=design.boundary_design_id,
        authorization_certification_id=design.authorization_certification_id, authorization_id=authorization.authorization_id,
        injection_id=injected.injection_id, transport_object_id=injected.transport_object_id,
        transport_identity_id=injected.transport_identity_id, status="certified", blockers=(),
        lineage_identity_verified=True, consumption_expiry_revocation_verified=True, readonly_scope_verified=True,
        audit_verified=True, zero_consumed_reserved_network_verified=True, certified_at=now.isoformat(),
    )
    reservation = ResearchRealProviderNetworkExecutionReservation(
        reservation_id="h38-reservation", boundary_certification_id=h37.certification_id,
        boundary_design_id=design.boundary_design_id, authorization_id=authorization.authorization_id,
        injection_id=injected.injection_id, transport_object_id=injected.transport_object_id,
        transport_identity_id=injected.transport_identity_id, operator_id=injected.operator_id,
        provider_id=injected.provider_id, capability=injected.capability, endpoint=injected.endpoint,
        allowed_method="GET", request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref=injected.transport_ref, authorization_expires_at=expires,
        state="authorization-consumed-request-reserved-network-disabled", authorization_consumed=True,
        request_reserved=True, reserved_request_count=1, revocable=True, revoked=False,
        network_execution_enabled=False, credential_resolution_enabled=False, provider_write_enabled=False,
        production_transport_enabled=False, reserved_at=now.isoformat(),
    )
    return reservation, h37, design, authorization, injected


def test_h39_certifies_clean_consumed_reserved_state(tmp_path):
    reservation, h37, design, authorization, injected = fixtures()
    result = ResearchRealProviderNetworkExecutionGateCertifier(tmp_path / "h39.db").certify(
        reservation, h37, design, authorization, injected
    )
    assert result.status == "certified"
    assert result.blockers == ()
    assert result.lineage_identity_verified is True
    assert result.exactly_once_reservation_verified is True
    assert result.expiry_revocation_verified is True
    assert result.readonly_scope_verified is True
    assert result.zero_provider_traffic_verified is True


def test_h39_blocks_double_reservation_or_network_activity(tmp_path):
    reservation, h37, design, authorization, injected = fixtures()
    bad = replace(reservation, reserved_request_count=2, requests_used=1, network_execution_enabled=True)
    result = ResearchRealProviderNetworkExecutionGateCertifier(tmp_path / "h39.db").certify(
        bad, h37, design, authorization, injected
    )
    assert result.status == "blocked"
    assert "authorization-consumption-or-single-request-reservation-invalid" in result.blockers
    assert "provider-traffic-credential-write-or-production-enabled" in result.blockers


def test_h39_blocks_lineage_scope_or_expiry_drift(tmp_path):
    reservation, h37, design, authorization, injected = fixtures()
    bad = replace(reservation, transport_identity_id="other", request_budget=3,
                  authorization_expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    result = ResearchRealProviderNetworkExecutionGateCertifier(tmp_path / "h39.db").certify(
        bad, h37, design, authorization, injected
    )
    assert result.status == "blocked"
    assert "h38-h37-h36-h35-h34-h33-h32-h31-h30-lineage-identity-mismatch" in result.blockers
    assert "reservation-expiry-or-revocation-state-invalid" in result.blockers
    assert "reserved-request-readonly-scope-invalid" in result.blockers


def test_h39_accepts_revoked_reservation_only_while_network_disabled(tmp_path):
    reservation, h37, design, authorization, injected = fixtures()
    revoked = replace(reservation, revoked=True, state="reservation-revoked-network-disabled")
    result = ResearchRealProviderNetworkExecutionGateCertifier(tmp_path / "h39.db").certify(
        revoked, h37, design, authorization, injected
    )
    assert result.status == "certified"
    assert result.expiry_revocation_verified is True
    assert result.zero_provider_traffic_verified is True


def test_h39_readiness_advances_to_h40_without_provider_traffic():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.647"
    assert r["next_item"] == "H40-research-real-provider-request-execution-design"
    assert r["real_provider_network_execution_gate_certified"] is True
    assert r["real_provider_network_execution_authorization_consumed"] is True
    assert r["real_provider_network_execution_request_reserved"] is True
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
