from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.auron_integration_readiness_v21_640 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignError,
    ResearchRealProviderNetworkExecutionAuthorizationDesignRegistry,
)
from app.research.auron_research_real_provider_transport_object_injection_certification_v21_639 import (
    ResearchRealProviderTransportObjectInjectionCertification,
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


def certification(i):
    return ResearchRealProviderTransportObjectInjectionCertification(
        certification_id="h31-cert",
        injection_id=i.injection_id,
        transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_verified=True,
        uniqueness_identity_verified=True,
        scope_fingerprint_verified=True,
        revocation_verified=True,
        zero_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h32_designs_short_lived_one_shot_authorization_without_enabling_network(tmp_path):
    i = injected()
    c = certification(i)
    design = ResearchRealProviderNetworkExecutionAuthorizationDesignRegistry(tmp_path / "h32.db").register(
        c, i, operator_id="operator-1", authorization_ttl_seconds=180
    )
    assert design.authorization_ttl_seconds == 180
    assert design.authorization_consumption_limit == 1
    assert design.authorization_issued is False
    assert design.authorization_consumed is False
    assert design.network_execution_enabled is False
    assert design.credential_resolution_enabled is False
    assert design.provider_write_enabled is False
    assert design.state == "designed-not-issued-not-consumed-network-disabled"


def test_h32_rejects_revoked_network_enabled_or_operator_mismatch(tmp_path):
    i = injected()
    c = certification(i)
    registry = ResearchRealProviderNetworkExecutionAuthorizationDesignRegistry(tmp_path / "h32.db")

    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="operator mismatch"):
        registry.register(c, i, operator_id="operator-2")
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="active revocable"):
        registry.register(c, replace(i, revoked=True), operator_id="operator-1")
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="zero network"):
        registry.register(c, replace(i, network_execution_enabled=True), operator_id="operator-1")


def test_h32_rejects_unsafe_ttl_scope_or_unclean_certification(tmp_path):
    i = injected()
    c = certification(i)
    registry = ResearchRealProviderNetworkExecutionAuthorizationDesignRegistry(tmp_path / "h32.db")

    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="ttl"):
        registry.register(c, i, operator_id="operator-1", authorization_ttl_seconds=301)
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="read-only GET"):
        registry.register(c, replace(i, allowed_method="POST"), operator_id="operator-1")
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationDesignError, match="clean H31"):
        registry.register(replace(c, status="blocked"), i, operator_id="operator-1")


def test_h32_readiness_advances_to_h33_without_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.640"
    assert r["next_item"] == "H33-research-real-provider-network-execution-authorization-design-certification"
    assert r["real_provider_network_execution_authorization_designed"] is True
    assert r["real_provider_network_execution_authorization_issued"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
