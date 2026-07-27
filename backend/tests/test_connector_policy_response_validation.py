import pytest

from app.schemas.connector_policy_response_validation import (
    ConnectorPolicyAction,
    ConnectorPolicyCreate,
    ConnectorPolicyProfile,
    ConnectorResponseAcceptAction,
    ConnectorResponseEnvelope,
)
from app.services.connector_policy_response_validation import ConnectorPolicyResponseValidationService


def policy_payload(**profile_overrides):
    profile = ConnectorPolicyProfile(
        connector_id="github-readonly-adapter",
        connector_type="github",
        allowed_content_types=["application/json"],
        required_fields=["id", "name"],
        allowed_top_level_fields=["id", "name", "token", "description"],
        redact_fields=["token", "authorization", "password", "secret", "api_key"],
        deny_fields=["private_key", "seed_phrase", "raw_credential"],
        **profile_overrides,
    )
    return ConnectorPolicyCreate(
        workspace_id="ws-a", source_key="github-policy", requested_by="owner", profile=profile
    )


def activate(service):
    record = service.create_policy(policy_payload())
    record = service.act_policy(record.record_id, ConnectorPolicyAction(
        workspace_id="ws-a", action="approve", actor="owner", operation_id="op-1"
    ))
    record = service.act_policy(record.record_id, ConnectorPolicyAction(
        workspace_id="ws-a", action="activate", actor="owner", operation_id="op-2"
    ))
    return record


def test_status_reports_response_security_boundary():
    status = ConnectorPolicyResponseValidationService().status()
    assert status["version"] == "21.121"
    assert status["response_sanitization_enabled"] is True
    assert status["schema_validation_enabled"] is True
    assert status["raw_response_forwarding_enabled"] is False
    assert status["write_execution_enabled"] is False
    assert status["trading_execution_enabled"] is False


def test_response_is_sanitized_validated_and_accepted():
    service = ConnectorPolicyResponseValidationService()
    policy = activate(service)
    response = service.ingest_response(ConnectorResponseEnvelope(
        workspace_id="ws-a", operation_id="response-1", policy_record_id=policy.record_id,
        connector_id="github-readonly-adapter", content_type="application/json", response_bytes=512,
        payload={"id": 1, "name": "repo", "token": "secret-token", "description": "<b>safe</b>", "unknown": "drop-me"},
    ))
    assert response.state.value == "validated"
    assert response.sanitized_payload["token"] == "[REDACTED]"
    assert response.sanitized_payload["description"] == "safe"
    assert "unknown" in response.removed_fields
    accepted = service.accept_response(response.response_id, ConnectorResponseAcceptAction(
        workspace_id="ws-a", operation_id="accept-1", actor="validator"
    ))
    assert accepted.state.value == "accepted"


def test_missing_required_field_rejects_response():
    service = ConnectorPolicyResponseValidationService()
    policy = activate(service)
    response = service.ingest_response(ConnectorResponseEnvelope(
        workspace_id="ws-a", operation_id="response-1", policy_record_id=policy.record_id,
        connector_id="github-readonly-adapter", content_type="application/json", response_bytes=100,
        payload={"id": 1},
    ))
    assert response.state.value == "rejected"
    assert "missing-required-field:name" in response.validation_errors


def test_response_size_and_content_type_are_enforced():
    service = ConnectorPolicyResponseValidationService()
    policy = activate(service)
    with pytest.raises(ValueError, match="size limit"):
        service.ingest_response(ConnectorResponseEnvelope(
            workspace_id="ws-a", operation_id="response-big", policy_record_id=policy.record_id,
            connector_id="github-readonly-adapter", content_type="application/json", response_bytes=2_000_000,
            payload={"id": 1, "name": "repo"},
        ))
    with pytest.raises(ValueError, match="content type"):
        service.ingest_response(ConnectorResponseEnvelope(
            workspace_id="ws-a", operation_id="response-html", policy_record_id=policy.record_id,
            connector_id="github-readonly-adapter", content_type="text/html", response_bytes=100,
            payload={"id": 1, "name": "repo"},
        ))


def test_critical_unsafe_policy_is_hard_blocked():
    service = ConnectorPolicyResponseValidationService()
    record = service.create_policy(policy_payload(
        criticality=0.98, allow_unknown_fields=True, require_schema_validation=False
    ))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_replay_workspace_and_duplicate_source_protection():
    service = ConnectorPolicyResponseValidationService()
    record = service.create_policy(policy_payload())
    service.act_policy(record.record_id, ConnectorPolicyAction(
        workspace_id="ws-a", action="approve", actor="owner", operation_id="same-op"
    ))
    with pytest.raises(ValueError, match="replay"):
        service.act_policy(record.record_id, ConnectorPolicyAction(
            workspace_id="ws-a", action="activate", actor="owner", operation_id="same-op"
        ))
    with pytest.raises(KeyError):
        service.get_policy("ws-b", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create_policy(policy_payload())
