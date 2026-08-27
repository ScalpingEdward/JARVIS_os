from dataclasses import replace
from datetime import datetime

import pytest

from app.core.auron_integration_readiness_v21_631 import get_integration_readiness
from app.research.auron_research_real_provider_transport_injection_activation_design_certification_v21_630 import (
    ResearchRealProviderTransportInjectionActivationDesignCertification,
)
from app.research.auron_research_real_provider_transport_injection_activation_design_v21_629 import (
    ResearchRealProviderTransportInjectionActivationDesign,
)
from app.research.auron_research_real_provider_transport_injection_authorization_gate_v21_631 import (
    ResearchRealProviderTransportInjectionAuthorizationGate,
    ResearchRealProviderTransportInjectionAuthorizationGateError,
)


def design():
    return ResearchRealProviderTransportInjectionActivationDesign(
        activation_design_id="h21-design",
        certification_id="h20-cert",
        contract_id="h19-contract",
        session_id="h18-session",
        operator_id="operator-1",
        provider_id="research-provider",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        allowed_method="GET",
        request_budget=2,
        timeout_seconds=10,
        max_response_bytes=1_048_576,
        transport_ref="transportref://research/sandbox/v1",
        state="designed-not-authorized-not-injected",
        read_only_required=True,
        operator_reapproval_required=True,
        kill_switch_required=True,
        rollback_required=True,
        exact_endpoint_required=True,
        exact_capability_required=True,
        fail_closed_budget_required=True,
        injection_authorized=False,
        transport_injected=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        created_at="2026-08-27T00:00:00+00:00",
    )


def certification():
    return ResearchRealProviderTransportInjectionActivationDesignCertification(
        certification_id="h22-cert",
        activation_design_id="h21-design",
        status="certified",
        blockers=(),
        exact_binding_verified=True,
        opaque_reference_verified=True,
        safety_controls_verified=True,
        zero_authorization_transport_verified=True,
        certified_at="2026-08-27T00:00:00+00:00",
    )


def authorize(tmp_path, *, d=None, c=None, **overrides):
    kwargs = dict(
        operator_id="operator-1",
        operator_reapproved=True,
        kill_switch_ready=True,
        rollback_ready=True,
        ttl_seconds=120,
    )
    kwargs.update(overrides)
    return ResearchRealProviderTransportInjectionAuthorizationGate(
        tmp_path / "auth.db"
    ).authorize(c or certification(), d or design(), **kwargs)


def test_h23_issues_short_lived_operator_bound_authorization_without_transport(tmp_path):
    auth = authorize(tmp_path)
    assert auth.state == "authorized-not-injected-not-executable"
    assert auth.injection_authorized is True
    assert auth.transport_injected is False
    assert auth.network_execution_enabled is False
    assert auth.credential_resolution_enabled is False
    assert auth.provider_write_enabled is False
    assert auth.production_transport_enabled is False
    issued = datetime.fromisoformat(auth.issued_at)
    expires = datetime.fromisoformat(auth.expires_at)
    assert 0 < (expires - issued).total_seconds() <= 300


def test_h23_requires_fresh_operator_reapproval_and_safety_readiness(tmp_path):
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, operator_reapproved=False)
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, kill_switch_ready=False)
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, rollback_ready=False)


def test_h23_blocks_unclean_certification_or_design_drift(tmp_path):
    blocked = replace(certification(), status="blocked", blockers=("drift",))
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, c=blocked)

    drifted = replace(design(), network_execution_enabled=True)
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, d=drifted)


def test_h23_one_authorization_per_h22_certification_is_idempotent(tmp_path):
    gate = ResearchRealProviderTransportInjectionAuthorizationGate(tmp_path / "auth.db")
    kwargs = dict(
        operator_id="operator-1",
        operator_reapproved=True,
        kill_switch_ready=True,
        rollback_ready=True,
        ttl_seconds=120,
    )
    first = gate.authorize(certification(), design(), **kwargs)
    second = gate.authorize(certification(), design(), **kwargs)
    assert first.authorization_id == second.authorization_id


def test_h23_ttl_is_bounded(tmp_path):
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, ttl_seconds=0)
    with pytest.raises(ResearchRealProviderTransportInjectionAuthorizationGateError):
        authorize(tmp_path, ttl_seconds=301)


def test_h23_readiness_advances_without_transport_injection():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.631"
    assert r["next_item"] == "H24-research-real-provider-transport-injection-boundary-design"
    assert r["real_provider_transport_injection_authorization_gate_enabled"] is True
    assert r["real_provider_transport_injection_authorized"] is True
    assert r["real_provider_transport_injected"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
