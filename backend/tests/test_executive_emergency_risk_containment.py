from uuid import uuid4

import pytest

from app.executive_emergency_risk_containment.models import (
    ContainmentActionRequest,
    ContainmentReleaseRequest,
    EmergencyContainmentAssessmentCreate,
    EmergencyContainmentObservation,
    EmergencyContainmentState,
    EmergencyTrigger,
)
from app.executive_emergency_risk_containment.service import executive_emergency_risk_containment_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_emergency_risk_containment_service.reset()


def payload(**overrides):
    values = {
        "account_risk_state": "daily-loss-breached",
        "trigger_confirmed": True,
        "kill_switch_active": True,
        "new_order_block_active": True,
        "pending_orders_present": False,
        "pending_orders_cancelled": True,
        "open_positions_present": True,
        "human_approval_verified": True,
        "liquidation_dispatched": True,
        "liquidation_acknowledged": True,
        "remaining_open_positions": 0,
        "remaining_pending_orders": 0,
        "broker_equity_reconciled": True,
        "broker_balance_reconciled": True,
        "position_state_reconciled": True,
        "incident_recorded": True,
    }
    values.update(overrides)
    return EmergencyContainmentAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        account_reference="prop-100k",
        broker_reference="broker-a",
        trigger=EmergencyTrigger.daily_loss,
        observation=EmergencyContainmentObservation(**values),
    )


def test_containment_completed() -> None:
    record = executive_emergency_risk_containment_service.assess(payload())
    assert record.state == EmergencyContainmentState.contained
    assert record.positions_liquidated is True


def test_account_risk_dependency() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(account_risk_state="account-risk-clear"))
    assert record.state == EmergencyContainmentState.account_risk_required


def test_trigger_confirmation_required() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(trigger_confirmed=False))
    assert record.state == EmergencyContainmentState.trigger_not_confirmed


def test_kill_switch_required() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(kill_switch_active=False))
    assert record.state == EmergencyContainmentState.blocked


def test_pending_order_cancellation() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(pending_orders_present=True, pending_orders_cancelled=False, remaining_pending_orders=2))
    assert record.state == EmergencyContainmentState.cancellation_pending


def test_liquidation_approval_required() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(human_approval_verified=False))
    assert record.state == EmergencyContainmentState.approval_required


def test_liquidation_pending() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(liquidation_acknowledged=False, remaining_open_positions=1))
    assert record.state == EmergencyContainmentState.liquidation_pending


def test_final_reconciliation_required() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(broker_equity_reconciled=False))
    assert record.state == EmergencyContainmentState.reconciliation_required


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    assert executive_emergency_risk_containment_service.assess(request).state == EmergencyContainmentState.blocked


def test_duplicate_rejected_and_workspace_isolated() -> None:
    request = payload()
    record = executive_emergency_risk_containment_service.assess(request)
    assert executive_emergency_risk_containment_service.get(record.id, "other") is None
    with pytest.raises(ValueError):
        executive_emergency_risk_containment_service.assess(request)


def test_approved_containment_action() -> None:
    record = executive_emergency_risk_containment_service.assess(payload(human_approval_verified=False))
    result = executive_emergency_risk_containment_service.contain(ContainmentActionRequest(workspace_id=record.workspace_id, containment_id=record.containment_id, actor_id="master-brano", human_approval_verified=True))
    assert result.state == EmergencyContainmentState.contained


def test_approved_release() -> None:
    record = executive_emergency_risk_containment_service.assess(payload())
    result = executive_emergency_risk_containment_service.release(ContainmentReleaseRequest(workspace_id=record.workspace_id, containment_id=record.containment_id, actor_id="master-brano", human_approval_verified=True))
    assert result.state == EmergencyContainmentState.released
    assert result.kill_switch_active is False
