from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auron_integration_readiness_v21_624 import get_integration_readiness
from app.research.auron_research_real_provider_activation_boundary_certification_v21_622 import (
    ResearchRealProviderActivationBoundaryCertification,
)
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import (
    ResearchRealProviderActivationBoundaryDesignRegistry,
)
from app.research.auron_research_real_provider_canary_execution_boundary_design_v21_624 import (
    ResearchRealProviderCanaryExecutionBoundaryDesignError,
    ResearchRealProviderCanaryExecutionBoundaryDesignRegistry,
)
from app.research.auron_research_real_provider_one_shot_canary_activation_gate_v21_623 import (
    ResearchRealProviderOneShotCanaryActivationGate,
)


def make_token(tmp_path):
    design = ResearchRealProviderActivationBoundaryDesignRegistry(tmp_path / "h13.db").register(
        skeleton_certification_id="h12-cert",
        provider_id="research-provider",
        environment="sandbox",
        capability="search-readonly",
        endpoint="https://sandbox.example.test/search",
        credential_ref="secretref://research/provider/read-only",
        operator_id="operator-1",
        max_requests=2,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    )
    certification = ResearchRealProviderActivationBoundaryCertification(
        "h14-cert",
        design.design_id,
        "certified",
        (),
        True,
        True,
        True,
        True,
        datetime.now(timezone.utc).isoformat(),
    )
    return ResearchRealProviderOneShotCanaryActivationGate(tmp_path / "h15.db").issue(
        certification,
        design,
        operator_id="operator-1",
        operator_reapproved=True,
        kill_switch_ready=True,
        rollback_ready=True,
        ttl_seconds=120,
    )


def test_h16_persists_exactly_once_bounded_zero_transport_design(tmp_path):
    token = make_token(tmp_path)
    registry = ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(tmp_path / "h16.db")
    boundary = registry.register(token, operator_id="operator-1")

    assert boundary.token_id == token.token_id
    assert boundary.token_consumption_limit == 1
    assert boundary.session_request_budget == token.request_budget == 2
    assert boundary.endpoint == token.endpoint
    assert boundary.capability == token.capability
    assert boundary.consumption_semantics == "consume-token-exactly-once-to-open-one-bounded-session"
    assert boundary.endpoint_enforcement == "exact-token-endpoint-only"
    assert boundary.capability_enforcement == "exact-token-capability-only"
    assert boundary.budget_enforcement == "fail-closed-counter-not-exceed-session-request-budget"
    assert "no-raw-secrets" in boundary.audit_semantics
    assert not boundary.audit_request_body_persisted
    assert not boundary.audit_raw_credential_persisted
    assert not boundary.transport_implementation_present
    assert not boundary.credential_resolution_enabled
    assert not boundary.provider_write_enabled
    assert not boundary.production_transport_enabled

    same = registry.register(token, operator_id="operator-1")
    assert same.boundary_id == boundary.boundary_id


def test_h16_rejects_revoked_expired_or_operator_mismatched_token(tmp_path):
    token = make_token(tmp_path)
    registry = ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(tmp_path / "h16.db")

    with pytest.raises(ResearchRealProviderCanaryExecutionBoundaryDesignError):
        registry.register(replace(token, state="revoked"), operator_id="operator-1")

    with pytest.raises(ResearchRealProviderCanaryExecutionBoundaryDesignError):
        registry.register(
            replace(
                token,
                expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            ),
            operator_id="operator-1",
        )

    with pytest.raises(ResearchRealProviderCanaryExecutionBoundaryDesignError):
        registry.register(token, operator_id="other")


def test_h16_rejects_transport_enabled_or_unbounded_token(tmp_path):
    token = make_token(tmp_path)
    registry = ResearchRealProviderCanaryExecutionBoundaryDesignRegistry(tmp_path / "h16.db")

    with pytest.raises(ResearchRealProviderCanaryExecutionBoundaryDesignError):
        registry.register(
            replace(token, network_execution_enabled=True), operator_id="operator-1"
        )

    with pytest.raises(ResearchRealProviderCanaryExecutionBoundaryDesignError):
        registry.register(replace(token, request_budget=11), operator_id="operator-1")


def test_h16_readiness_advances_to_h17_without_execution():
    readiness = get_integration_readiness()
    assert readiness["roadmap_version"] == "v21.624"
    assert readiness["next_item"] == "H17-research-real-provider-canary-execution-boundary-certification"
    assert readiness["real_provider_canary_execution_boundary_designed"] is True
    assert readiness["real_provider_canary_execution_enabled"] is False
    assert readiness["external_provider_network_enabled"] is False
    assert readiness["external_provider_credential_resolution_enabled"] is False
    assert readiness["live_transports_enabled"] is False
