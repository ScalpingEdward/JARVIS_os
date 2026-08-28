from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_648 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_gate_certification_v21_647 import (
    ResearchRealProviderNetworkExecutionGateCertification,
)
from app.research.auron_research_real_provider_network_execution_gate_v21_646 import (
    ResearchRealProviderNetworkExecutionReservation,
)
from app.research.auron_research_real_provider_request_execution_design_v21_648 import (
    ResearchRealProviderRequestExecutionDesignError,
    ResearchRealProviderRequestExecutionDesignRegistry,
)


def reservation():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderNetworkExecutionReservation(
        reservation_id="h38-reservation",
        boundary_certification_id="h37-cert",
        boundary_design_id="h36-boundary",
        authorization_id="h34-auth",
        injection_id="h30-injection",
        transport_object_id="transport-object-1",
        transport_identity_id="transport-identity-1",
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
        authorization_expires_at=(now + timedelta(seconds=180)).isoformat(),
        state="authorization-consumed-request-reserved-network-disabled",
        authorization_consumed=True,
        request_reserved=True,
        reserved_request_count=1,
        revocable=True,
        revoked=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        reserved_at=now.isoformat(),
    )


def certification(r):
    return ResearchRealProviderNetworkExecutionGateCertification(
        certification_id="h39-cert",
        reservation_id=r.reservation_id,
        boundary_certification_id=r.boundary_certification_id,
        boundary_design_id=r.boundary_design_id,
        authorization_id=r.authorization_id,
        injection_id=r.injection_id,
        transport_object_id=r.transport_object_id,
        transport_identity_id=r.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_identity_verified=True,
        exactly_once_reservation_verified=True,
        expiry_revocation_verified=True,
        readonly_scope_verified=True,
        zero_provider_traffic_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h40_designs_one_immutable_unexecuted_readonly_request(tmp_path):
    r = reservation(); c = certification(r)
    d = ResearchRealProviderRequestExecutionDesignRegistry(tmp_path / "h40.db").register(c, r)

    assert d.gate_certification_id == c.certification_id
    assert d.reservation_id == r.reservation_id
    assert d.immutable_request_id.startswith("research-real-request-")
    assert d.transport_call_signature.startswith("GET(")
    assert d.authorization_consumed is True
    assert d.request_reserved is True
    assert d.reserved_request_count == 1
    assert d.request_executed is False
    assert d.network_execution_enabled is False
    assert d.state == "designed-reservation-certified-request-unexecuted-network-disabled"


def test_h40_is_deterministic_and_idempotent_for_same_certification(tmp_path):
    r = reservation(); c = certification(r)
    registry = ResearchRealProviderRequestExecutionDesignRegistry(tmp_path / "h40.db")
    first = registry.register(c, r)
    second = registry.register(c, r)
    assert first.request_execution_design_id == second.request_execution_design_id
    assert first.immutable_request_id == second.immutable_request_id


def test_h40_rejects_revoked_or_already_used_reservation(tmp_path):
    r = reservation(); c = certification(r)
    registry = ResearchRealProviderRequestExecutionDesignRegistry(tmp_path / "h40.db")
    with pytest.raises(ResearchRealProviderRequestExecutionDesignError, match="active revocable reservation"):
        registry.register(c, replace(r, revoked=True))
    with pytest.raises(ResearchRealProviderRequestExecutionDesignError, match="remain unused"):
        registry.register(c, replace(r, requests_used=1))


def test_h40_rejects_scope_or_execution_state_drift(tmp_path):
    r = reservation(); c = certification(r)
    registry = ResearchRealProviderRequestExecutionDesignRegistry(tmp_path / "h40.db")
    with pytest.raises(ResearchRealProviderRequestExecutionDesignError, match="read-only GET only"):
        registry.register(c, replace(r, allowed_method="POST"))
    with pytest.raises(ResearchRealProviderRequestExecutionDesignError, match="zero provider execution state"):
        registry.register(c, replace(r, network_execution_enabled=True))


def test_h40_rejects_nonclean_h39_certification(tmp_path):
    r = reservation(); c = certification(r)
    blocked = replace(c, status="blocked", blockers=("unsafe",))
    with pytest.raises(ResearchRealProviderRequestExecutionDesignError, match="clean H39 certification required"):
        ResearchRealProviderRequestExecutionDesignRegistry(tmp_path / "h40.db").register(blocked, r)


def test_h40_readiness_advances_to_h41_without_provider_traffic():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.648"
    assert r["next_item"] == "H41-research-real-provider-request-execution-design-certification"
    assert r["real_provider_request_execution_designed"] is True
    assert r["real_provider_request_execution_attempted"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
