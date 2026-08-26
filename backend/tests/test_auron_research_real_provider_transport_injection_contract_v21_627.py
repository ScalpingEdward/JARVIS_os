from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_627 import get_integration_readiness
from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import (
    ResearchRealProviderCanaryExecutionSession,
)
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import (
    ResearchRealProviderTransportInjectionContractError,
    ResearchRealProviderTransportInjectionContractRegistry,
    ResearchRealProviderTransportRequest,
)


def session():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderCanaryExecutionSession(
        session_id="h18-session",
        certification_id="h17-cert",
        boundary_id="h16-boundary",
        token_id="h15-token",
        operator_id="operator-1",
        provider_id="research-provider",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        request_budget=2,
        requests_used=0,
        state="token-consumed-session-open-transport-disabled",
        opened_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        transport_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def test_h19_registers_design_only_transport_contract(tmp_path):
    registry = ResearchRealProviderTransportInjectionContractRegistry(tmp_path / "h19.db")
    c = registry.register(session(), timeout_seconds=5, max_response_bytes=4096)
    assert c.state == "defined-not-injected"
    assert c.allowed_method == "GET"
    assert c.request_budget == 2
    assert c.timeout_seconds == 5
    assert c.max_response_bytes == 4096
    assert c.exact_endpoint_required
    assert c.exact_capability_required
    assert c.fail_closed_budget_required
    assert c.transport_interface_defined
    assert not c.concrete_transport_present
    assert not c.network_execution_enabled
    assert not c.credential_resolution_enabled
    assert not c.provider_write_enabled
    assert not c.production_transport_enabled


def test_h19_contract_is_idempotent_per_session(tmp_path):
    registry = ResearchRealProviderTransportInjectionContractRegistry(tmp_path / "h19.db")
    s = session()
    first = registry.register(s)
    second = registry.register(s)
    assert first.contract_id == second.contract_id


def test_h19_rejects_enabled_or_used_session(tmp_path):
    registry = ResearchRealProviderTransportInjectionContractRegistry(tmp_path / "h19.db")
    with pytest.raises(ResearchRealProviderTransportInjectionContractError):
        registry.register(replace(session(), transport_injected=True))
    with pytest.raises(ResearchRealProviderTransportInjectionContractError):
        registry.register(replace(session(), requests_used=1))


def test_h19_validates_future_request_shape_without_transport(tmp_path):
    registry = ResearchRealProviderTransportInjectionContractRegistry(tmp_path / "h19.db")
    c = registry.register(session(), timeout_seconds=5)
    request = ResearchRealProviderTransportRequest(
        method="GET",
        endpoint=c.endpoint,
        capability=c.capability,
        request_index=1,
        timeout_seconds=5,
        headers={"accept": "application/json"},
    )
    registry.validate_request(c, request, requests_used=0)


def test_h19_fail_closed_endpoint_capability_budget_and_method(tmp_path):
    registry = ResearchRealProviderTransportInjectionContractRegistry(tmp_path / "h19.db")
    c = registry.register(session(), timeout_seconds=5)
    base = ResearchRealProviderTransportRequest(
        method="GET",
        endpoint=c.endpoint,
        capability=c.capability,
        request_index=1,
        timeout_seconds=5,
        headers={},
    )
    for bad in (
        replace(base, method="POST"),
        replace(base, endpoint="https://other.example.test/search"),
        replace(base, capability="other-capability"),
        replace(base, request_index=2),
        replace(base, body=b"forbidden"),
    ):
        with pytest.raises(ResearchRealProviderTransportInjectionContractError):
            registry.validate_request(c, bad, requests_used=0)
    exhausted = replace(base, request_index=3)
    with pytest.raises(ResearchRealProviderTransportInjectionContractError):
        registry.validate_request(c, exhausted, requests_used=2)


def test_h19_readiness_advances_to_h20_without_transport_enablement():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.627"
    assert r["next_item"] == "H20-research-real-provider-transport-injection-contract-certification"
    assert r["real_provider_transport_injection_contract_defined"] is True
    assert r["real_provider_transport_configured"] is False
    assert r["real_provider_canary_transport_enabled"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
