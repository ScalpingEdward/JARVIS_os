from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.auron_integration_readiness_v21_643 import get_integration_readiness
from app.research.auron_research_real_provider_network_execution_authorization_certification_v21_643 import (
    ResearchRealProviderNetworkExecutionAuthorizationCertifier,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_v21_640 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesign,
)
from app.research.auron_research_real_provider_network_execution_authorization_design_certification_v21_641 import (
    ResearchRealProviderNetworkExecutionAuthorizationDesignCertification,
)
from app.research.auron_research_real_provider_network_execution_authorization_gate_v21_642 import (
    ResearchRealProviderNetworkExecutionAuthorization,
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


def design(i):
    return ResearchRealProviderNetworkExecutionAuthorizationDesign(
        authorization_design_id="h32-design",
        injection_certification_id="h31-cert",
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


def h33(d, i):
    return ResearchRealProviderNetworkExecutionAuthorizationDesignCertification(
        certification_id="h33-cert",
        authorization_design_id=d.authorization_design_id,
        injection_certification_id=d.injection_certification_id,
        injection_id=i.injection_id,
        transport_object_id=i.transport_object_id,
        transport_identity_id=i.transport_identity_id,
        status="certified",
        blockers=(),
        lineage_identity_verified=True,
        ttl_one_shot_verified=True,
        scope_verified=True,
        approval_controls_verified=True,
        audit_zero_network_verified=True,
        certified_at=datetime.now(timezone.utc).isoformat(),
    )


def authorization(d, i):
    now = datetime.now(timezone.utc)
    return ResearchRealProviderNetworkExecutionAuthorization(
        authorization_id="h34-auth",
        design_certification_id="h33-cert",
        authorization_design_id=d.authorization_design_id,
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
        state="authorized-not-consumed-network-disabled",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=d.authorization_ttl_seconds)).isoformat(),
        authorization_issued=True,
        authorization_consumed=False,
        revocable=True,
        revoked=False,
        network_execution_enabled=False,
        credential_resolution_enabled=False,
        provider_write_enabled=False,
        production_transport_enabled=False,
    )


def test_h35_certifies_clean_unconsumed_authorization(tmp_path):
    i = injected()
    d = design(i)
    c = h33(d, i)
    a = authorization(d, i)
    result = ResearchRealProviderNetworkExecutionAuthorizationCertifier(tmp_path / "h35.db").certify(a, c, d, i)

    assert result.status == "certified"
    assert result.blockers == ()
    assert result.lineage_identity_verified is True
    assert result.ttl_expiry_verified is True
    assert result.one_shot_scope_verified is True
    assert result.revocation_verified is True
    assert result.zero_consumed_network_verified is True


def test_h35_blocks_consumed_or_network_enabled_authorization(tmp_path):
    i = injected()
    d = design(i)
    c = h33(d, i)
    a = replace(authorization(d, i), authorization_consumed=True, network_execution_enabled=True)
    result = ResearchRealProviderNetworkExecutionAuthorizationCertifier(tmp_path / "h35.db").certify(a, c, d, i)

    assert result.status == "blocked"
    assert "authorization-consumed-or-network-state-enabled" in result.blockers


def test_h35_blocks_ttl_or_identity_drift(tmp_path):
    i = injected()
    d = design(i)
    c = h33(d, i)
    a = authorization(d, i)
    bad_expiry = (datetime.fromisoformat(a.issued_at) + timedelta(seconds=90)).isoformat()
    a = replace(a, expires_at=bad_expiry, transport_identity_id="other-identity")
    result = ResearchRealProviderNetworkExecutionAuthorizationCertifier(tmp_path / "h35.db").certify(a, c, d, i)

    assert result.status == "blocked"
    assert "h34-h33-h32-h31-h30-lineage-identity-mismatch" in result.blockers
    assert "authorization-ttl-or-expiry-invalid" in result.blockers


def test_h35_accepts_revoked_authorization_only_as_network_disabled(tmp_path):
    i = injected()
    d = design(i)
    c = h33(d, i)
    a = replace(authorization(d, i), revoked=True, state="revoked-network-disabled")
    result = ResearchRealProviderNetworkExecutionAuthorizationCertifier(tmp_path / "h35.db").certify(a, c, d, i)

    assert result.status == "certified"
    assert result.revocation_verified is True
    assert result.zero_consumed_network_verified is True


def test_h35_readiness_advances_to_h36_without_execution():
    r = get_integration_readiness()
    assert r["roadmap_version"] == "v21.643"
    assert r["next_item"] == "H36-research-real-provider-network-execution-boundary-design"
    assert r["real_provider_network_execution_authorization_certified"] is True
    assert r["real_provider_network_execution_authorization_consumed"] is False
    assert r["external_provider_network_enabled"] is False
    assert r["real_provider_canary_execution_enabled"] is False
