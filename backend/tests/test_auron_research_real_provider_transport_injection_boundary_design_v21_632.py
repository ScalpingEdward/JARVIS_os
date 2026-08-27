from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_632 import get_integration_readiness
from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorization,
)
from app.research.auron_research_real_provider_transport_injection_boundary_design_v21_632 import (
    ResearchRealProviderTransportInjectionBoundaryDesignError,
    ResearchRealProviderTransportInjectionBoundaryDesignRegistry,
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


def test_h24_registers_design_without_consuming_or_injecting(tmp_path):
    a = authorization()
    b = ResearchRealProviderTransportInjectionBoundaryDesignRegistry(
        tmp_path / "h24.db"
    ).register(a, operator_id="operator-1")

    assert b.authorization_id == a.authorization_id
    assert b.authorization_consumption_limit == 1
    assert b.authorization_consumption_semantics == (
        "consume-authorization-exactly-once-to-bind-one-transport-instance"
    )
    assert b.transport_identity_semantics == "exact-authorization-transport-ref-instance-only"
    assert b.state == "designed-not-consumed-not-injected"
    assert b.authorization_consumed is False
    assert b.transport_identity_bound is False
    assert b.transport_injected is False
    assert b.network_execution_enabled is False
    assert b.credential_resolution_enabled is False
    assert b.provider_write_enabled is False


def test_h24_rejects_expired_authorization(tmp_path):
    a = authorization()
    expired = replace(
        a,
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
    )
    with pytest.raises(
        ResearchRealProviderTransportInjectionBoundaryDesignError,
        match="expired",
    ):
        ResearchRealProviderTransportInjectionBoundaryDesignRegistry(
            tmp_path / "h24.db"
        ).register(expired, operator_id="operator-1")


def test_h24_rejects_scope_or_transport_drift(tmp_path):
    a = authorization()
    for drifted in (
        replace(a, allowed_method="POST"),
        replace(a, request_budget=11),
        replace(a, transport_ref="raw-transport-object"),
        replace(a, transport_injected=True),
        replace(a, network_execution_enabled=True),
    ):
        with pytest.raises(ResearchRealProviderTransportInjectionBoundaryDesignError):
            ResearchRealProviderTransportInjectionBoundaryDesignRegistry(
                tmp_path / f"{hash(str(drifted))}.db"
            ).register(drifted, operator_id="operator-1")


def test_h24_is_idempotent_per_authorization(tmp_path):
    a = authorization()
    registry = ResearchRealProviderTransportInjectionBoundaryDesignRegistry(
        tmp_path / "h24.db"
    )
    first = registry.register(a, operator_id="operator-1")
    second = registry.register(a, operator_id="operator-1")
    assert first.boundary_id == second.boundary_id


def test_h24_readiness_advances_to_h25_without_transport_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.632"
    assert r["next_item"] == "H25-research-real-provider-transport-injection-boundary-certification"
    assert r["real_provider_transport_injection_boundary_designed"] is True
    assert r["real_provider_transport_injection_authorization_consumed"] is False
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
