import pytest
from pydantic import ValidationError

from app.data_governance.models import (
    ActionState, ActionType, DataAssetCreate, DataClass,
    GovernanceActionCreate, LegalHoldCreate, Mutation, PolicyState,
    PrivacyRequestCreate, RequestType, RetentionPolicyCreate,
)
from app.data_governance.service import DataGovernanceService


def policy_payload(workspace: str = "ws-1") -> RetentionPolicyCreate:
    return RetentionPolicyCreate(
        workspace_id=workspace,
        owner_id="owner",
        policy_key="audit.logs",
        name="Audit retention",
        target_modules=["audit"],
        data_classes=[DataClass.CONFIDENTIAL],
        retention_days=30,
        expiry_action=ActionType.ARCHIVE,
        legal_basis="legitimate_interest",
    )


def test_policy_asset_and_workspace_isolation() -> None:
    service = DataGovernanceService()
    policy = service.create_policy(policy_payload())
    service.set_policy_state(policy.id, "ws-1", Mutation(requester_id="owner"), PolicyState.ACTIVE)
    asset = service.create_asset(DataAssetCreate(
        workspace_id="ws-1",
        owner_id="owner",
        asset_key="audit:1",
        source_module="audit",
        data_class=DataClass.CONFIDENTIAL,
        purpose="security audit",
        legal_basis="legitimate_interest",
        policy_id=policy.id,
    ))
    assert asset.expires_at is not None
    assert service.list_assets("ws-2") == []


def test_legal_hold_blocks_delete_plan_completion() -> None:
    service = DataGovernanceService()
    asset = service.create_asset(DataAssetCreate(
        workspace_id="ws-1",
        owner_id="owner",
        asset_key="document:1",
        source_module="documents",
        data_class=DataClass.RESTRICTED,
        purpose="legal evidence",
        legal_basis="legal_claim",
    ))
    service.create_hold(LegalHoldCreate(
        workspace_id="ws-1",
        owner_id="owner",
        hold_key="case-1",
        reason="active dispute",
        asset_ids=[asset.id],
    ))
    action = service.create_action(GovernanceActionCreate(
        workspace_id="ws-1",
        owner_id="owner",
        asset_id=asset.id,
        action_type=ActionType.DELETE,
        reason="retention expired",
    ))
    assert action.state == ActionState.BLOCKED
    assert service.set_action_state(action.id, "ws-1", Mutation(requester_id="owner"), ActionState.COMPLETED) is None


def test_privacy_request_is_planning_only() -> None:
    with pytest.raises(ValidationError):
        PrivacyRequestCreate(
            workspace_id="ws-1",
            owner_id="owner",
            requester_id="subject",
            subject_reference="subject:1",
            request_type=RequestType.EXPORT,
            execute_external_action=True,
        )


def test_plaintext_and_secret_assets_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DataAssetCreate(
            workspace_id="ws-1",
            owner_id="owner",
            asset_key="secret:1",
            source_module="connector",
            data_class=DataClass.RESTRICTED,
            purpose="integration",
            legal_basis="contract",
            contains_secret=True,
        )
    with pytest.raises(ValidationError):
        DataAssetCreate(
            workspace_id="ws-1",
            owner_id="owner",
            asset_key="raw:1",
            source_module="memory",
            data_class=DataClass.CONFIDENTIAL,
            purpose="memory",
            legal_basis="consent",
            raw_content="sensitive body",
        )


def test_automatic_deletion_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RetentionPolicyCreate(
            workspace_id="ws-1",
            owner_id="owner",
            policy_key="unsafe",
            name="Unsafe",
            retention_days=1,
            legal_basis="test",
            automatic_delete=True,
        )
