from datetime import datetime, timedelta, timezone

import pytest

from app.config_feature_flags.models import (
    ApprovalCreate, ConfigEntryCreate, ConfigState, Environment, EvaluationRequest,
    FeatureFlagCreate, FlagState, Mutation,
)
from app.config_feature_flags.service import ConfigFeatureService


def flag_payload(**overrides):
    data = dict(workspace_id="ws", owner_id="owner", flag_key="new.dashboard", name="New dashboard", environment=Environment.TEST, rollout_percentage=100)
    data.update(overrides)
    return FeatureFlagCreate(**data)


def test_flag_requires_review_approval_and_owner_cannot_self_approve():
    service = ConfigFeatureService()
    flag = service.create_flag(flag_payload())
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.REVIEW)
    with pytest.raises(ValueError, match="self-approval"):
        service.approve_flag(ApprovalCreate(workspace_id="ws", requester_id="owner", flag_id=flag.id))
    service.approve_flag(ApprovalCreate(workspace_id="ws", requester_id="reviewer", flag_id=flag.id))
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.APPROVED)
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.ACTIVE)
    result = service.evaluate(EvaluationRequest(workspace_id="ws", flag_key="new.dashboard", environment=Environment.TEST, subject_id="user-1"))
    assert result.enabled is True


def test_dependency_gate_blocks_activation():
    service = ConfigFeatureService()
    flag = service.create_flag(flag_payload(flag_key="dependent", dependency_flag_keys=["missing"]))
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.REVIEW)
    service.approve_flag(ApprovalCreate(workspace_id="ws", requester_id="reviewer", flag_id=flag.id))
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.APPROVED)
    with pytest.raises(ValueError, match="dependency"):
        service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.ACTIVE)


def test_expired_flag_is_disabled():
    service = ConfigFeatureService()
    flag = service.create_flag(flag_payload(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.REVIEW)
    service.approve_flag(ApprovalCreate(workspace_id="ws", requester_id="reviewer", flag_id=flag.id))
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.APPROVED)
    service.set_flag_state(flag.id, "ws", Mutation(requester_id="owner"), FlagState.ACTIVE)
    result = service.evaluate(EvaluationRequest(workspace_id="ws", flag_key="new.dashboard", environment=Environment.TEST, subject_id="user-1"))
    assert result.enabled is False
    assert result.reason == "flag-expired"


def test_configuration_versions_and_safety():
    service = ConfigFeatureService()
    payload = ConfigEntryCreate(workspace_id="ws", owner_id="owner", namespace="risk", key="daily_limit", environment=Environment.STAGING, value=2.5)
    first = service.create_config(payload)
    second = service.create_config(payload)
    assert first.version == 1
    assert second.version == 2
    with pytest.raises(ValueError, match="never apply"):
        ConfigEntryCreate(workspace_id="ws", owner_id="owner", namespace="risk", key="unsafe", environment=Environment.PRODUCTION, value=True, apply_change=True)


def test_workspace_isolation():
    service = ConfigFeatureService()
    flag = service.create_flag(flag_payload())
    assert service.get_flag(flag.id, "other") is None
    assert service.list_flags("other") == []
