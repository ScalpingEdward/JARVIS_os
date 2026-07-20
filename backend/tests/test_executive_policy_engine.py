from uuid import uuid4

import pytest

from app.executive_policy_engine.models import (
    ActionKind,
    PolicyDecisionState,
    PolicyEffect,
    PolicyEvaluationCreate,
    PolicyObservation,
    PolicyRule,
)
from app.executive_policy_engine.service import ExecutivePolicyEngineService


def valid_payload(workspace_id: str = "ws-1") -> PolicyEvaluationCreate:
    rule = PolicyRule(
        policy_id="allow-workflow",
        action_kinds=[ActionKind.workflow_dispatch],
        effect=PolicyEffect.allow,
        workspace_scope_verified=True,
        role_scope_verified=True,
    )
    return PolicyEvaluationCreate(
        workspace_id=workspace_id,
        source_key=f"source-{uuid4()}",
        actor_id="actor-1",
        actor_role="operator",
        observability_assessment_id="obs-1",
        observability_state="healthy",
        action_kind=ActionKind.workflow_dispatch,
        action_target="workflow:alpha",
        observation=PolicyObservation(
            policy_set_loaded=True,
            policy_version_resolved=True,
            inheritance_resolved=True,
            actor_role_resolved=True,
            action_context_valid=True,
            observability_context_linked=True,
            audit_sink_available=True,
            matched_rules=[rule],
        ),
    )


def test_policy_approved_for_dispatch() -> None:
    service = ExecutivePolicyEngineService()
    record = service.create(valid_payload())
    assert record.state == PolicyDecisionState.ready_for_dispatch
    assert record.allowed is True


def test_deny_overrides_allow() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.observation.matched_rules.append(
        PolicyRule(policy_id="deny-workflow", priority=1, action_kinds=[ActionKind.workflow_dispatch], effect=PolicyEffect.deny)
    )
    record = service.create(payload)
    assert record.state == PolicyDecisionState.policy_denied
    assert record.allowed is False


def test_human_approval_required() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.observation.matched_rules = [
        PolicyRule(policy_id="approve-first", action_kinds=[ActionKind.workflow_dispatch], effect=PolicyEffect.require_approval)
    ]
    record = service.create(payload)
    assert record.state == PolicyDecisionState.approval_required


def test_maintenance_blocks_mutation() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.mutating_action = True
    payload.observation.maintenance_mode_enabled = True
    record = service.create(payload)
    assert record.state == PolicyDecisionState.maintenance_mode


def test_kill_switch_blocks_all() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.observation.kill_switch_enabled = True
    record = service.create(payload)
    assert record.state == PolicyDecisionState.blocked


def test_risk_brain_blocks() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.risk_brain_clear = False
    record = service.create(payload)
    assert record.state == PolicyDecisionState.blocked


def test_raw_policy_secrets_blocked() -> None:
    service = ExecutivePolicyEngineService()
    payload = valid_payload()
    payload.observation.raw_policy_secrets_present = True
    record = service.create(payload)
    assert record.state == PolicyDecisionState.blocked


def test_duplicate_evaluation_rejected() -> None:
    service = ExecutivePolicyEngineService()
    first = valid_payload()
    service.create(first)
    second = valid_payload()
    second.evaluation_id = first.evaluation_id
    with pytest.raises(ValueError, match="Duplicate policy evaluation"):
        service.create(second)


def test_workspace_isolation() -> None:
    service = ExecutivePolicyEngineService()
    record = service.create(valid_payload("ws-a"))
    assert service.get(record.id, "ws-b") is None
    assert service.list_evaluations("ws-b") == []
