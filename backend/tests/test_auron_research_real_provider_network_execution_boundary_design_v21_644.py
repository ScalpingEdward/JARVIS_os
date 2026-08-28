from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_644 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_certification_v21_643 import (
    ResearchRealProviderNetworkExecutionAuthorizationCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
)
from app.research.auron_research_real_provider_network_execution_boundary_design_v21_644 import (
    ResearchRealProviderNetworkExecutionBoundaryDesignError,
    ResearchRealProviderNetworkExecutionBoundaryDesignRegistry,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


def injected():
    return ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection",
        design_certification_id="h29-cert",
        injection_design_id="h28-design",
        binding_id="h26-binding",
        transport_identity_id="transport-identity-1",
        transport_object_id="transport-object-1",
        transport_object_fingerprint="fingerprint-1",
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
        state="transport-object-injected-network-disabled",
        transport_object_present=True,
        transport_object_injected=True,
        revocable=True,
        revoked=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        injected_at=datetime.now(timezone.utc).isoformat(),
    )


def authorization(i):
    now = datetime.now(timezone.utc)
    return ResearchRealProviderNetworkExecutionAuthorization(
        authorization_id="h34-auth",
        design_certification_id="h33-cert",
        authorization_design_id="h32-design",
        injection_id=i.injection_id,
        transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id,
        operator_id=i.operator_id,
        provider_id=i.provider_id,
        capability=i.capability,
        endpoint=i.endpoint,
        allowed_method=i.allowed_method,
        request_budget=i.request_budget,
        requests_used=0,
        timeout_seconds=i.timeout_seconds,
        max_response_bytes=i.max_response_bytes,
        transport_ref=i.transport_ref,
        state="authorized-not-consumed-network-disabled",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=180)).isoformat(),
        authorization_issued=True,
        authorization_consumed=False,
        revocable=True,
        revoked=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def certification(a, i):
    return ResearchRealProviderNetworkExecutionAuthorizationCertification(
        certification_id="h35-cert",
        authorization_id=a.authorization_id,
        authorization_design_id=a.authorization_design_id,
        injection_id=i.injection_id,
        transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_identity_verified=True,
        ttl_expiry_verified=True,
        one_shot_scope_verified=True,
        revocation_verified=True,
        zero_consumed_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h36_designs_exactly_once_boundary_without_consumption(tmp_path):
    i = injected()
    a = authorization(i)
    c = certification(a, i)
    design = ResearchRealProviderNetworkExecutionBoundaryDesignRegistry(tmp_path / "h36.db").register(c, a, i)

    assert design.consumption_limit == 1
    assert design.authorization_consumed is False
    assert design.request_reserved is False
    assert design.network_execution_enabled is False
    assert design.state == "designed-authorization-unconsumed-request-unreserved-network-disabled"


def test_h36_rejects_consumed_or_network_enabled_authorization(tmp_path):
    i = injected()
    a = replace(authorization(i), authorization_consumed=True, network_execution_enabled=True)
    c = certification(a, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionBoundaryDesignError):
        ResearchRealProviderNetworkExecutionBoundaryDesignRegistry(tmp_path / "h36.db").register(c, a, i)


def test_h36_rejects_revoked_or_identity_drift(tmp_path):
    i = injected()
    a = authorization(i)
    c = certification(a, i)
    with pytest.raises(ResearchRealProviderNetworkExecutionBoundaryDesignError):
        ResearchRealProviderNetworkExecutionBoundaryDesignRegistry(tmp_path / "h36.db").register(c, replace(a, revoked=True), i)
    with pytest.raises(ResearchRealProviderNetworkExecutionBoundaryDesignError):
        ResearchRealProviderNetworkExecutionBoundaryDesignRegistry(tmp_path / "h36b.db").register(
            replace(c, transport_identity_id="other"), a, i
        )


def test_h36_readiness_advances_to_h37_without_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.644"
    assert r["next_item"] == "H37-research-real-provider-network-execution-boundary-certification"
    assert r["real_provider_network_execution_boundary_designed"] is True
    assert r["real_provider_network_execution_authorization_consumed"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
