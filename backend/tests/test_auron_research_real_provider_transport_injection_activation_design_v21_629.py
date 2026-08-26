from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_629 import get_integration_readiness
from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import ResearchRealProviderCanaryExecutionSession
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import ResearchRealProviderTransportInjectionContract
from app.research.auron_research_real_provider_transport_injection_contract_certification_v21_628 import ResearchRealProviderTransportInjectionContractCertification
from app.research.auron_research_real_provider_transport_injection_activation_design_v21_629 import ResearchRealProviderTransportInjectionActivationDesignError, ResearchRealProviderTransportInjectionActivationDesignRegistry


def session():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderCanaryExecutionSession("session-1", "h17-cert", "boundary-1", "token-1", "operator-1", "research-provider", "search-readonly", "https://sandbox.example.test/search", 2, 0, "token-consumed-session-open-transport-disabled", now.isoformat(), (now + timedelta(minutes=5)).isoformat(), False, False, False, False, False)


def contract(s):
    return ResearchRealProviderTransportInjectionContract("contract-1", s.session_id, s.provider_id, s.capability, s.endpoint, "GET", s.request_budget, 10, 1048576, "defined-not-injected", True, True, True, True, False, False, False, False, False)


def cert(c, s):
    return ResearchRealProviderTransportInjectionContractCertification("h20-cert", c.contract_id, s.session_id, "certified", (), True, True, True, True, True, True, datetime.now(timezone.utc).isoformat())


def test_h21_registers_zero_transport_activation_design(tmp_path):
    s = session(); c = contract(s); h20 = cert(c, s)
    d = ResearchRealProviderTransportInjectionActivationDesignRegistry(tmp_path / "h21.db").register(h20, c, s, operator_id="operator-1", transport_ref="transportref://research/read-only/canary-1")
    assert d.state == "designed-not-authorized-not-injected"
    assert d.read_only_required and d.operator_reapproval_required and d.kill_switch_required and d.rollback_required
    assert not d.injection_authorized and not d.transport_injected and not d.network_execution_enabled


def test_h21_requires_clean_h20_and_exact_binding(tmp_path):
    s = session(); c = contract(s); h20 = cert(c, s); r = ResearchRealProviderTransportInjectionActivationDesignRegistry(tmp_path / "h21.db")
    with pytest.raises(ResearchRealProviderTransportInjectionActivationDesignError):
        r.register(replace(h20, status="blocked", blockers=("x",)), c, s, operator_id="operator-1", transport_ref="transportref://x")
    with pytest.raises(ResearchRealProviderTransportInjectionActivationDesignError):
        r.register(h20, replace(c, endpoint="https://other.test"), s, operator_id="operator-1", transport_ref="transportref://x")


def test_h21_rejects_nonopaque_ref_and_transport_drift(tmp_path):
    s = session(); c = contract(s); h20 = cert(c, s); r = ResearchRealProviderTransportInjectionActivationDesignRegistry(tmp_path / "h21.db")
    with pytest.raises(ResearchRealProviderTransportInjectionActivationDesignError):
        r.register(h20, c, s, operator_id="operator-1", transport_ref="raw-secret-or-client")
    with pytest.raises(ResearchRealProviderTransportInjectionActivationDesignError):
        r.register(h20, replace(c, concrete_transport_present=True), s, operator_id="operator-1", transport_ref="transportref://x")


def test_h21_is_idempotent_per_h20_certification(tmp_path):
    s = session(); c = contract(s); h20 = cert(c, s); r = ResearchRealProviderTransportInjectionActivationDesignRegistry(tmp_path / "h21.db")
    a = r.register(h20, c, s, operator_id="operator-1", transport_ref="transportref://research/read-only/canary-1")
    b = r.register(h20, c, s, operator_id="operator-1", transport_ref="transportref://research/read-only/canary-1")
    assert a.activation_design_id == b.activation_design_id


def test_h21_readiness_advances_to_h22_without_authorization():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.629"
    assert r["next_item"] == "H22-research-real-provider-transport-injection-activation-design-certification"
    assert r["real_provider_transport_injection_activation_designed"] is True
    assert r["real_provider_transport_injection_authorized"] is False
    assert r["real_provider_canary_transport_enabled"] is False
    assert r["external_provider_network_enabled"] is False
