import pytest

from app.schemas.agent_authorization_tool_use import AgentAuthorizationCreate
from app.services.agent_authorization_tool_use import AgentAuthorizationToolUseService


def _payload(**overrides):
    observation = {
        "agent_id": "research-agent-1",
        "agent_version": "1.0.0",
        "role": "research",
        "tool_name": "market-data-read",
        "tool_category": "read-only-data",
        "requested_scope": 0.30,
        "approved_scope": 0.35,
        "least_privilege_score": 0.95,
        "authorization_coverage": 1.0,
        "human_approval_coverage": 1.0,
        "tool_allowlist_coverage": 1.0,
        "delegation_control_score": 0.95,
        "prompt_injection_resilience": 0.95,
        "data_access_control_score": 0.95,
        "output_validation_score": 0.95,
        "auditability_score": 1.0,
        "reversibility_score": 1.0,
        "confidence": 0.95,
        "freshness": 1.0,
        "unauthorized_tool_attempts": 0,
        "unapproved_delegations": 0,
        "prompt_injection_events": 0,
        "sensitive_data_access_events": 0,
        "autonomous_high_impact_actions": 0,
        "business_criticality": 0.60,
    }
    observation.update(overrides.pop("observation", {}))
    payload = {
        "workspace_id": "workspace-a",
        "source_key": "agent-auth-001",
        "requested_by": "risk-owner",
        "observations": [observation],
    }
    payload.update(overrides)
    return AgentAuthorizationCreate(**payload)


def test_status_is_advisory_only():
    service = AgentAuthorizationToolUseService()
    status = service.status()
    assert status["version"] == "21.87"
    assert status["agent_execution_enabled"] is False
    assert status["tool_permission_mutation_enabled"] is False
    assert status["credential_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True


def test_healthy_agent_tool_pair_can_be_approved_and_activated():
    service = AgentAuthorizationToolUseService()
    record = service.create(_payload())
    assert record.risk_flags == []
    assessed = service.act("workspace-a", record.record_id, "assess", "owner", "op-1")
    assert assessed.state.value == "assessed"
    reviewed = service.act("workspace-a", record.record_id, "submit-review", "owner", "op-2")
    assert reviewed.state.value == "review-required"
    approved = service.act("workspace-a", record.record_id, "approve", "human-approver", "op-3")
    assert approved.approved_by == "human-approver"
    active = service.act("workspace-a", record.record_id, "activate", "human-approver", "op-4")
    assert active.state.value == "active"


def test_scope_excess_blocks_approval():
    service = AgentAuthorizationToolUseService()
    record = service.create(_payload(observation={"requested_scope": 0.90, "approved_scope": 0.20}))
    assert any(flag.startswith("scope-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("workspace-a", record.record_id, "approve", "owner", "op-a")


def test_prompt_injection_event_is_flagged():
    service = AgentAuthorizationToolUseService()
    record = service.create(_payload(observation={"prompt_injection_events": 1}))
    assert any(flag.startswith("injection-alert:") for flag in record.risk_flags)
    assert record.dispositions[0].lifecycle_signal == "injection-alert"


def test_unauthorized_high_impact_action_on_critical_agent_hard_blocks():
    service = AgentAuthorizationToolUseService()
    record = service.create(
        _payload(
            observation={
                "business_criticality": 0.95,
                "autonomous_high_impact_actions": 1,
            }
        )
    )
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_operation_replay_is_rejected():
    service = AgentAuthorizationToolUseService()
    record = service.create(_payload())
    service.act("workspace-a", record.record_id, "assess", "owner", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("workspace-a", record.record_id, "monitor", "owner", "same-op")


def test_workspace_isolation():
    service = AgentAuthorizationToolUseService()
    record = service.create(_payload())
    with pytest.raises(KeyError):
        service.get("workspace-b", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = AgentAuthorizationToolUseService()
    service.create(_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(_payload())


def test_duplicate_agent_tool_pair_is_rejected():
    base = _payload().model_dump()
    base["source_key"] = "agent-auth-dup"
    base["observations"] = [base["observations"][0], base["observations"][0]]
    with pytest.raises(ValueError, match="duplicate agent/tool observation"):
        AgentAuthorizationCreate(**base)
