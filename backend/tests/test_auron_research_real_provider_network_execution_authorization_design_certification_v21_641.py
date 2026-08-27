from dataclasses import replace
from datetime import datetime, timezone

from app.core.auron_integration_readiness_v21_641 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_design_certification_v21_641 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesign,
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


def h31(i):
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


def design(i, c):
    return ResearchRealProviderNetworkExecutionAuthorizationDesign(
        authorization_design_id="h32-design",
        injection_certification_id=c.certification_id,
        injection_id=i.injection_id,
        transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id,
        operator_id=i.operator_id,
        provider_id=i.provider_id,
        capability=i.capability,
        endpoint=i.endpoint,
        allowed_method=i.allowed_method,
        request_budget=i.request_budget,
        requests_used=0,
        timeout_seconds=i.timeout_seconds,
        max_response_bytes=i.max_response_bytes,
        transport_ref=i.transport_ref,
        authorization_ttl_seconds=180,
        authorization_consumption_limit=1,
        authorization_semantics="short-lived-operator-bound-exact-scope-one-shot-network-authorization",
        reapproval_semantics="fresh-explicit-reapproval-required-before-authorization-issuance",
        kill_switch_semantics="kill-switch-must-be-clear-before-issuance-and-invalidates-authorization",
        rollback_semantics="rollback-readiness-required-before-issuance",
        audit_semantics="append-only-metadata-and-hashes-no-raw-credentials-request-or-response-bodies",
        state="designed-not-issued-not-consumed-network-disabled",
        authorization_issued=False,
        authorization_consumed=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def test_h33_certifies_clean_h32_design(tmp_path):
    i = injected()
    c = h31(i)
    d = design(i, c)
    result = ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier(tmp_path / "h33.db").certify(d, c, i)
    assert result.status == "certified"
    assert not result.blockers
    assert result.lineage_identity_verified
    assert result.ttl_one_shot_verified
    assert result.scope_verified
    assert result.approval_controls_verified
    assert result.audit_zero_network_verified


def test_h33_blocks_ttl_or_one_shot_drift(tmp_path):
    i = injected()
    c = h31(i)
    d = replace(design(i, c), authorization_ttl_seconds=301, authorization_consumption_limit=2)
    result = ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier(tmp_path / "h33.db").certify(d, c, i)
    assert result.status == "blocked"
    assert "authorization-ttl-or-one-shot-semantics-invalid" in result.blockers


def test_h33_blocks_scope_drift(tmp_path):
    i = injected()
    c = h31(i)
    d = replace(design(i, c), request_budget=3)
    result = ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier(tmp_path / "h33.db").certify(d, c, i)
    assert result.status == "blocked"
    assert "network-authorization-scope-invalid" in result.blockers


def test_h33_blocks_issued_or_network_enabled_state(tmp_path):
    i = injected()
    c = h31(i)
    d = replace(design(i, c), authorization_issued=True, network_execution_enabled=True)
    result = ResearchRealProviderNetworkExecutionAuthorizationDesignCertifier(tmp_path / "h33.db").certify(d, c, i)
    assert result.status == "blocked"
    assert "authorization-ttl-or-one-shot-semantics-invalid" in result.blockers
    assert "audit-or-zero-issued-zero-network-state-invalid" in result.blockers


def test_h33_readiness_advances_to_h34_without_network():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.641"
    assert r["next_item"] == "H34-research-real-provider-network-execution-authorization-gate"
    assert r["real_provider_network_execution_authorization_design_certified"] is True
    assert r["real_provider_network_execution_authorization_issued"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["live_transports_enabled"] is False
