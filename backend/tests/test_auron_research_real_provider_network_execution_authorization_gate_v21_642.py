from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.auron_integration_readiness_v21_642 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesign,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_certification_v21_641 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorizationGate,
    ResearchRealProviderNetworkExecutionAuthorizationGateError,
)
from app.research.auron_research_real_provider_transport_object_injection_gate_v21_638 import (
    ResearchRealProviderInjectedTransportObject,
)


def injected():
    return ResearchRealProviderInjectedTransportObject(
        injection_id="h30-injection", design_certification_id="h29-cert", injection_design_id="h28-design",
        binding_id="h26-binding", transport_identity_id="identity-1", transport_object_id="object-1",
        transport_object_fingerprint="fp", operator_id="operator-1", provider_id="research-provider",
        capability="search-readonly", endpoint="https://sandbox.example.test/search", allowed_method="GET",
        request_budget=2, requests_used=0, timeout_seconds=10, max_response_bytes=1024,
        transport_ref="transportref://research-provider/read-only-canary",
        state="transport-object-injected-network-disabled", transport_object_present=True,
        transport_object_injected=True, revocable=True, revoked=False, network_execution_enabled=False,
        credential_resolution_enabled=False, provider_write_enabled=False, production_transport_enabled=False,
        injected_at=datetime.now(timezone.utc).isoformat(),
    )


def design(i):
    return ResearchRealProviderNetworkExecutionAuthorizationDesign(
        authorization_design_id="h32-design", injection_certification_id="h31-cert",
        injection_id=i.injection_id, transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id, operator_id=i.operator_id,
        provider_id=i.provider_id, capability=i.capability, endpoint=i.endpoint,
        allowed_method=i.allowed_method, request_budget=i.request_budget, requests_used=0,
        timeout_seconds=i.timeout_seconds, max_response_bytes=i.max_response_bytes,
        transport_ref=i.transport_ref, authorization_ttl_seconds=180, authorization_consumption_limit=1,
        authorization_semantics="short-lived-operator-bound-exact-scope-one-shot-network-authorization",
        reapproval_semantics="fresh-explicit-reapproval-required-before-authorization-issuance",
        kill_switch_semantics="kill-switch-must-be-clear-before-issuance-and-invalidates-authorization",
        rollback_semantics="rollback-readiness-required-before-issuance",
        audit_semantics="append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
        state="designed-not-issued-not-consumed-network-disabled", authorization_issued=False,
        authorization_consumed=False, network_execution_enabled=False, credential_resolution_enabled=False,
        provider_write_enabled=False, production_transport_enabled=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def certification(d, i):
    return ResearchRealProviderNetworkExecutionAuthorizationDesignCertification(
        certification_id="h33-cert", authorization_design_id=d.authorization_design_id,
        injection_certification_id=d.injection_certification_id, injection_id=i.injection_id,
        transport_object_id=i.transport_object_id, transport_identity_id=i.transport_identity_id,
        status="certified", blockers=(), lineage_identity_verified=True, ttl_one_shot_verified=True,
        scope_verified=True, approval_controls_verified=True, audit_zero_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h34_issues_short_lived_authorization_without_network(tmp_path):
    i = injected(); d = design(i); c = certification(d, i)
    a = ResearchRealProviderNetworkExecutionAuthorizationGate(tmp_path / "h34.db").issue(
        c, d, i, operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True
    )
    assert a.authorization_issued is True
    assert a.authorization_consumed is False
    assert a.revocable is True and a.revoked is False
    assert a.network_execution_enabled is False
    assert a.state == "authorized-not-consumed-network-disabled"


def test_h34_rejects_missing_controls_and_duplicate_issue(tmp_path):
    i = injected(); d = design(i); c = certification(d, i)
    gate = ResearchRealProviderNetworkExecutionAuthorizationGate(tmp_path / "h34.db")
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationGateError, match="reapproval"):
        gate.issue(c, d, i, operator_id="operator-1", fresh_reapproval=False, kill_switch_clear=True, rollback_ready=True)
    gate.issue(c, d, i, operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True)
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationGateError, match="already issued"):
        gate.issue(c, d, i, operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True)


def test_h34_rejects_revoked_or_network_enabled_object(tmp_path):
    i = injected(); d = design(i); c = certification(d, i)
    gate = ResearchRealProviderNetworkExecutionAuthorizationGate(tmp_path / "h34.db")
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationGateError, match="active revocable"):
        gate.issue(c, d, replace(i, revoked=True, state="transport-object-revoked-network-disabled"), operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True)
    with pytest.raises(ResearchRealProviderNetworkExecutionAuthorizationGateError, match="zero network"):
        gate.issue(c, d, replace(i, network_execution_enabled=True), operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True)


def test_h34_revocation_and_readiness(tmp_path):
    i = injected(); d = design(i); c = certification(d, i)
    gate = ResearchRealProviderNetworkExecutionAuthorizationGate(tmp_path / "h34.db")
    a = gate.issue(c, d, i, operator_id="operator-1", fresh_reapproval=True, kill_switch_clear=True, rollback_ready=True)
    r = gate.revoke(a.authorization_id)
    assert r.revoked is True and r.state == "revoked-network-disabled"
    readiness = get_integration_readiness()
    assert readiness["roadmap_version"] == "v21.642"
    assert readiness["next_item"] == "H35-research-real-provider-network-execution-authorization-certification"
    assert readiness["real_provider_network_execution_authorization_issued"] is True
    assert readiness["external_provider_network_enabled"] is False
