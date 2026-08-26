from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_628 import get_integration_readiness
from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import (
    ResearchRealProviderCanaryExecutionSession,
)
from app.research.auron_research_real_provider_transport_injection_contract_v21_627 import (
    ResearchRealProviderTransportInjectionContractRegistry,
)
from app.research.auron_research_real_provider_transport_injection_contract_certification_v21_628 import (
    ResearchRealProviderTransportInjectionContractCertifier,
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


def contract(tmp_path, s):
    return ResearchRealProviderTransportInjectionContractRegistry(
        tmp_path / "contract.db"
    ).register(s, timeout_seconds=10, max_response_bytes=65536)


def certify(tmp_path, c, s):
    return ResearchRealProviderTransportInjectionContractCertifier(
        tmp_path / "cert.db"
    ).certify(c, s)


def test_h20_certifies_clean_h19_contract_without_transport(tmp_path):
    s = session()
    c = contract(tmp_path, s)
    cert = certify(tmp_path, c, s)
    assert cert.status == "certified"
    assert cert.blockers == ()
    assert cert.session_binding_verified
    assert cert.interface_semantics_verified
    assert cert.endpoint_capability_verified
    assert cert.budget_sequence_verified
    assert cert.timeout_response_bounds_verified
    assert cert.zero_transport_verified


def test_h20_blocks_session_binding_and_interface_drift(tmp_path):
    s = session()
    c = contract(tmp_path, s)
    drifted = replace(
        c,
        provider_id="other-provider",
        allowed_method="POST",
        exact_endpoint_required=False,
    )
    cert = certify(tmp_path, drifted, s)
    assert cert.status == "blocked"
    assert "session-or-provider-contract-binding-mismatch" in cert.blockers
    assert "transport-interface-semantics-invalid" in cert.blockers


def test_h20_blocks_budget_bounds_and_transport_enablement(tmp_path):
    s = session()
    c = contract(tmp_path, s)
    drifted = replace(
        c,
        request_budget=11,
        timeout_seconds=31,
        max_response_bytes=1_048_577,
        concrete_transport_present=True,
        network_execution_enabled=True,
    )
    cert = certify(tmp_path, drifted, s)
    assert cert.status == "blocked"
    assert "session-or-provider-contract-binding-mismatch" in cert.blockers
    assert "request-budget-or-sequence-semantics-invalid" in cert.blockers
    assert "timeout-or-response-size-bounds-invalid" in cert.blockers
    assert "transport-credential-resolution-or-write-enabled" in cert.blockers


def test_h20_persistence_is_idempotent_per_contract(tmp_path):
    s = session()
    c = contract(tmp_path, s)
    certifier = ResearchRealProviderTransportInjectionContractCertifier(tmp_path / "cert.db")
    first = certifier.certify(c, s)
    second = certifier.certify(c, s)
    assert first.certification_id == second.certification_id


def test_h20_readiness_advances_to_h21_without_real_transport():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.628"
    assert r["next_item"] == "H21-research-real-provider-transport-injection-activation-design"
    assert r["real_provider_transport_injection_contract_certified"] is True
    assert r["real_provider_canary_transport_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["external_provider_credential_resolution_enabled"] is False
    assert r["live_transports_enabled"] is False
