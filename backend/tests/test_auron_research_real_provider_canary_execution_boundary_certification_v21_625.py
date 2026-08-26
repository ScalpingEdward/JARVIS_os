from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_625 import get_integration_readiness
from app.research.auron_research_real_provider_canary_execution_boundary_certification_v21_625 import (
    ResearchRealProviderCanaryExecutionBoundaryCertifier,
)
from app.research.auron_research_real_provider_canary_execution_boundary_design_v21_624 import (
    ResearchRealProviderCanaryExecutionBoundaryDesignRegistry,
)
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderCanaryActivationToken,
)


def token():
    now = datetime.now(timezone.utc)
    return ResearchRealProviderCanaryActivationToken(
        token_id="h15-token",
        certification_id="h14-cert",
        design_id="h13-design",
        operator_id="operator-1",
        provider_id="research-provider",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        request_budget=2,
        state="armed-not-executable",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def boundary(tmp_path, t):
    return ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(
        tmp_path / "boundary.db"
    ).register(t, operator_id="operator-1")


def certify(tmp_path, b, t):
    return ResearchRealProviderCanaryExecutionBoundaryCertifier(
        tmp_path / "cert.db"
    ).certify(
        b,
        t,
        expected_operator_id="operator-1",
        expected_provider_id="research-provider",
        expected_capability="search-readonly",
        allowed_endpoints=("https://sandbox.example.test/search",),
    )


def test_h17_certifies_clean_h16_design_without_execution(tmp_path):
    t = token()
    b = boundary(tmp_path, t)
    c = certify(tmp_path, b, t)
    assert c.status == "certified"
    assert c.blockers == ()
    assert c.token_binding_verified
    assert c.one_time_consumption_verified
    assert c.endpoint_capability_budget_verified
    assert c.audit_safety_verified
    assert c.zero_transport_verified


def test_h17_blocks_token_binding_mismatch(tmp_path):
    t = token()
    b = boundary(tmp_path, t)
    mismatched = replace(t, provider_id="other-provider")
    c = certify(tmp_path, b, mismatched)
    assert c.status == "blocked"
    assert "token-or-identity-binding-mismatch" in c.blockers


def test_h17_blocks_consumption_budget_audit_and_transport_drift(tmp_path):
    t = token()
    b = boundary(tmp_path, t)
    drifted = replace(
        b,
        token_consumption_limit=2,
        session_request_budget=11,
        audit_raw_credential_persisted=True,
        transport_implementation_present=True,
    )
    c = certify(tmp_path, drifted, t)
    assert c.status == "blocked"
    assert "one-time-consumption-semantics-invalid" in c.blockers
    assert "token-or-identity-binding-mismatch" in c.blockers
    assert "endpoint-capability-or-budget-enforcement-invalid" in c.blockers
    assert "audit-safety-invariants-invalid" in c.blockers
    assert "transport-credential-resolution-or-write-enabled" in c.blockers


def test_h17_persistence_is_idempotent_per_boundary(tmp_path):
    t = token()
    b = boundary(tmp_path, t)
    certifier = ResearchRealProviderCanaryExecutionBoundaryCertifier(tmp_path / "cert.db")
    kwargs = dict(
        expected_operator_id="operator-1",
        expected_provider_id="research-provider",
        expected_capability="search-readonly",
        allowed_endpoints=("https://sandbox.example.test/search",),
    )
    first = certifier.certify(b, t, **kwargs)
    second = certifier.certify(b, t, **kwargs)
    assert first.certification_id == second.certification_id


def test_h17_readiness_advances_to_h18_without_canary_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.625"
    assert r["next_item"] == "H18-research-real-provider-one-shot-canary-execution-gate"
    assert r["real_provider_canary_execution_boundary_certified"] is True
    assert r["real_provider_canary_execution_enabled"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["external_provider_credential_resolution_enabled"] is False
    assert r["live_transports_enabled"] is False
