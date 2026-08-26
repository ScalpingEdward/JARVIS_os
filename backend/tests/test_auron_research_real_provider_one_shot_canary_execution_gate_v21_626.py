from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_626 import get_integration_readiness
from app.research.auron_research_real_provider_canary_execution_boundary_certification_v21_625 import (
    ResearchRealProviderCanaryExecutionBoundaryCertifier,
)
from app.research.auron_research_real_provider_canary_execution_boundary_design_v21_624 import (
    ResearchRealProviderCanaryExecutionBoundaryDesignRegistry,
)
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderCanaryActivationToken,
)
from app.research.auron_research_real_provider_one_shot_canary_execution_gate_v21_626 import (
    ResearchRealProviderOneShotCanaryExecutionGate,
    ResearchRealProviderOneShotCanaryExecutionGateError,
)


def token(*, state="armed-not-executable", expires_delta=timedelta(minutes=5)):
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
        state=state,
        issued_at=now.isoformat(),
        expires_at=(now + expires_delta).isoformat(),
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def certified_stack(tmp_path, t):
    b = ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(
        tmp_path / "boundary.db"
    ).register(t, operator_id="operator-1")
    c = ResearchRealProviderCanaryExecutionBoundaryCertifier(
        tmp_path / "cert.db"
    ).certify(
        b,
        t,
        expected_operator_id="operator-1",
        expected_provider_id="research-provider",
        expected_capability="search-readonly",
        allowed_endpoints=("https://sandbox.example.test/search",),
    )
    return b, c


def test_h18_consumes_certified_token_once_and_opens_transport_disabled_session(tmp_path):
    t = token()
    b, c = certified_stack(tmp_path, t)
    gate = ResearchRealProviderOneShotCanaryExecutionGate(tmp_path / "gate.db")
    s = gate.open_session(c, b, t, operator_id="operator-1")
    assert s.token_id == t.token_id
    assert s.request_budget == 2 and s.requests_used == 0
    assert s.state == "token-consumed-session-open-transport-disabled"
    assert not s.transport_injected
    assert not s.network_execution_enabled
    assert not s.credential_resolution_enabled
    assert not s.provider_write_enabled
    assert not s.production_transport_enabled


def test_h18_rejects_second_consumption_of_same_token(tmp_path):
    t = token()
    b, c = certified_stack(tmp_path, t)
    gate = ResearchRealProviderOneShotCanaryExecutionGate(tmp_path / "gate.db")
    gate.open_session(c, b, t, operator_id="operator-1")
    with pytest.raises(ResearchRealProviderOneShotCanaryExecutionGateError, match="already consumed"):
        gate.open_session(c, b, t, operator_id="operator-1")


def test_h18_rejects_unclean_certification_and_contract_drift(tmp_path):
    t = token()
    b, c = certified_stack(tmp_path, t)
    gate = ResearchRealProviderOneShotCanaryExecutionGate(tmp_path / "gate.db")
    with pytest.raises(ResearchRealProviderOneShotCanaryExecutionGateError):
        gate.open_session(replace(c, status="blocked", blockers=("x",)), b, t, operator_id="operator-1")
    with pytest.raises(ResearchRealProviderOneShotCanaryExecutionGateError):
        gate.open_session(c, replace(b, capability="other"), t, operator_id="operator-1")


def test_h18_rejects_expired_or_revoked_token(tmp_path):
    expired = token(expires_delta=timedelta(seconds=-1))
    b = replace(
        ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(tmp_path / "expired-boundary.db").register(
            token(), operator_id="operator-1"
        ),
        token_id=expired.token_id,
        expires_at=expired.expires_at,
    )
    c = ResearchRealProviderCanaryExecutionBoundaryCertifier(tmp_path / "expired-cert.db").certify(
        b,
        expired,
        expected_operator_id="operator-1",
        expected_provider_id="research-provider",
        expected_capability="search-readonly",
        allowed_endpoints=("https://sandbox.example.test/search",),
    )
    gate = ResearchRealProviderOneShotCanaryExecutionGate(tmp_path / "gate.db")
    with pytest.raises(ResearchRealProviderOneShotCanaryExecutionGateError, match="expired"):
        gate.open_session(c, b, expired, operator_id="operator-1")

    revoked = token(state="revoked")
    rb = ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(tmp_path / "revoked-boundary.db").register(
        replace(revoked, state="armed-not-executable"), operator_id="operator-1"
    )
    rc = ResearchRealProviderCanaryExecutionBoundaryCertifier(tmp_path / "revoked-cert.db").certify(
        rb,
        replace(revoked, state="armed-not-executable"),
        expected_operator_id="operator-1",
        expected_provider_id="research-provider",
        expected_capability="search-readonly",
        allowed_endpoints=("https://sandbox.example.test/search",),
    )
    with pytest.raises(ResearchRealProviderOneShotCanaryExecutionGateError, match="not consumable"):
        gate.open_session(rc, rb, revoked, operator_id="operator-1")


def test_h18_readiness_advances_to_h19_without_network_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.626"
    assert r["next_item"] == "H19-research-real-provider-transport-injection-contract"
    assert r["real_provider_canary_session_gate_enabled"] is True
    assert r["real_provider_canary_transport_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
