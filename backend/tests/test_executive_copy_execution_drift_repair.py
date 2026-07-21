from uuid import uuid4

import pytest

from app.executive_copy_execution_drift_repair.models import (
    CopyExecutionAssessmentCreate,
    CopyExecutionObservation,
    CopyExecutionState,
    DriftRepairRequest,
    FollowerExecutionEvidence,
)
from app.executive_copy_execution_drift_repair.service import executive_copy_execution_drift_repair_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_copy_execution_drift_repair_service.reset()


def follower(**overrides) -> FollowerExecutionEvidence:
    values = {
        "account_reference": "follower-1",
        "intended": True,
        "dispatch_attempted": True,
        "broker_acknowledged": True,
        "broker_order_id_present": True,
        "symbol_matches": True,
        "side_matches": True,
        "volume_matches": True,
        "stop_loss_matches": True,
        "take_profit_matches": True,
        "position_present": True,
        "fill_price_drift_bps": 5,
        "volume_drift_pct": 1,
        "latency_ms": 250,
    }
    values.update(overrides)
    return FollowerExecutionEvidence(**values)


def payload(*, followers=None, **observation_overrides) -> CopyExecutionAssessmentCreate:
    observation_values = {
        "copy_governance_state": "copy-ready",
        "source_execution_state": "execution-completed",
        "source_position_state": "position-open",
        "fanout_requested": True,
        "source_execution_reconciled": True,
        "followers": followers or [follower()],
    }
    observation_values.update(observation_overrides)
    return CopyExecutionAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        copy_group_id=uuid4(),
        source_execution_id=uuid4(),
        source_account_reference="source-100k",
        canonical_symbol="XAUUSD",
        observation=CopyExecutionObservation(**observation_values),
    )


def test_copy_execution_synchronized() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload())
    assert record.state == CopyExecutionState.synchronized
    assert record.synchronized_followers == 1


def test_copy_governance_dependency() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(copy_governance_state="copy-suspended"))
    assert record.state == CopyExecutionState.copy_governance_required


def test_source_execution_dependency() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(source_execution_state="partial-fill"))
    assert record.state == CopyExecutionState.source_execution_required


def test_fanout_pending() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(fanout_requested=False))
    assert record.state == CopyExecutionState.fanout_pending


def test_follower_ack_pending() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(broker_acknowledged=False)]))
    assert record.state == CopyExecutionState.follower_ack_pending


def test_latency_drift_requires_approval() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(latency_ms=3000, repair_required=True)]))
    assert record.state == CopyExecutionState.repair_approval_required
    assert record.drifted_followers == 1


def test_mapping_drift_requires_approval() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(volume_matches=False)]))
    assert record.state == CopyExecutionState.repair_approval_required


def test_duplicate_execution_quarantined() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(duplicate_execution_detected=True)]))
    assert record.state == CopyExecutionState.quarantined
    assert record.quarantined_followers == 1


def test_approved_repair_pending() -> None:
    record = executive_copy_execution_drift_repair_service.assess(
        payload(followers=[follower(volume_matches=False, repair_human_approved=True, repair_dispatched=False)])
    )
    assert record.state == CopyExecutionState.repair_pending


def test_repair_completes_synchronization() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(volume_matches=False)]))
    repaired = executive_copy_execution_drift_repair_service.repair(
        DriftRepairRequest(
            workspace_id=record.workspace_id,
            fanout_id=record.fanout_id,
            actor_id="master-brano",
            human_approval_verified=True,
            repaired_accounts=["follower-1"],
            repair_dispatch_acknowledged=True,
            final_positions_reconciled=True,
            remaining_drifted_followers=0,
        )
    )
    assert repaired.state == CopyExecutionState.synchronized
    assert repaired.drifted_followers == 0


def test_repair_requires_human_approval() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload(followers=[follower(volume_matches=False)]))
    with pytest.raises(ValueError):
        executive_copy_execution_drift_repair_service.repair(
            DriftRepairRequest(
                workspace_id=record.workspace_id,
                fanout_id=record.fanout_id,
                actor_id="master-brano",
                human_approval_verified=False,
            )
        )


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    record = executive_copy_execution_drift_repair_service.assess(request)
    assert record.state == CopyExecutionState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_copy_execution_drift_repair_service.assess(request)
    with pytest.raises(ValueError):
        executive_copy_execution_drift_repair_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_copy_execution_drift_repair_service.assess(payload())
    assert executive_copy_execution_drift_repair_service.get(record.id, "other-workspace") is None
