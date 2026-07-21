from uuid import uuid4

import pytest

from app.executive_multi_account_copy_governance.models import AccountBinding, AccountRole, CopyControlRequest, CopyGovernanceAssessmentCreate, CopyGovernanceObservation, CopyGovernanceState, CopyMode
from app.executive_multi_account_copy_governance.service import executive_multi_account_copy_governance_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_multi_account_copy_governance_service.reset()


def payload(**overrides):
    observation_values = {"human_approval_verified": True}
    observation_values.update(overrides)
    return CopyGovernanceAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        copy_mode=CopyMode.risk_ratio,
        accounts=[
            AccountBinding(account_reference="source-100k", broker_reference="broker-a", role=AccountRole.source, balance=100000, equity=100000, current_open_risk_pct=1),
            AccountBinding(account_reference="follower-100k", broker_reference="broker-b", role=AccountRole.follower, balance=100000, equity=100000, current_open_risk_pct=1),
        ],
        observation=CopyGovernanceObservation(**observation_values),
    )


def test_copy_group_ready() -> None:
    record = executive_multi_account_copy_governance_service.assess(payload())
    assert record.state == CopyGovernanceState.copy_ready
    assert record.follower_count == 1


def test_single_source_required() -> None:
    request = payload()
    request.accounts[1].role = AccountRole.source
    assert executive_multi_account_copy_governance_service.assess(request).state == CopyGovernanceState.topology_invalid


def test_reentry_required() -> None:
    request = payload()
    request.accounts[1].controlled_reentry_state = "limited-trading"
    assert executive_multi_account_copy_governance_service.assess(request).state == CopyGovernanceState.reentry_required


def test_account_risk_required() -> None:
    request = payload()
    request.accounts[1].account_risk_state = "risk-reduction-required"
    assert executive_multi_account_copy_governance_service.assess(request).state == CopyGovernanceState.risk_mismatch


def test_mapping_degraded() -> None:
    assert executive_multi_account_copy_governance_service.assess(payload(symbol_mapping_complete=False)).state == CopyGovernanceState.synchronization_degraded


def test_latency_degraded() -> None:
    assert executive_multi_account_copy_governance_service.assess(payload(latency_ms=1500)).state == CopyGovernanceState.synchronization_degraded


def test_cross_account_hedge_rejected() -> None:
    assert executive_multi_account_copy_governance_service.assess(payload(cross_account_hedge_detected=True)).state == CopyGovernanceState.policy_rejected


def test_duplicate_dispatch_rejected() -> None:
    assert executive_multi_account_copy_governance_service.assess(payload(duplicate_dispatch_detected=True)).state == CopyGovernanceState.policy_rejected


def test_human_approval_required() -> None:
    assert executive_multi_account_copy_governance_service.assess(payload(human_approval_verified=False)).state == CopyGovernanceState.approval_required


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    assert executive_multi_account_copy_governance_service.assess(request).state == CopyGovernanceState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_multi_account_copy_governance_service.assess(request)
    with pytest.raises(ValueError):
        executive_multi_account_copy_governance_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_multi_account_copy_governance_service.assess(payload())
    assert executive_multi_account_copy_governance_service.get(record.id, "other") is None


def test_suspend_and_resume() -> None:
    record = executive_multi_account_copy_governance_service.assess(payload())
    control = CopyControlRequest(workspace_id=record.workspace_id, copy_group_id=record.copy_group_id, actor_id="master-brano", human_approval_verified=True)
    suspended = executive_multi_account_copy_governance_service.control(control, suspend=True)
    assert suspended.state == CopyGovernanceState.copy_suspended
    resumed = executive_multi_account_copy_governance_service.control(control, suspend=False)
    assert resumed.state == CopyGovernanceState.copy_ready
