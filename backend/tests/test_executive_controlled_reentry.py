from uuid import uuid4

import pytest

from app.executive_controlled_reentry.models import (
    CanaryResultRequest,
    ControlledReentryAssessmentCreate,
    ControlledReentryObservation,
    ControlledReentryState,
    FullReenableRequest,
)
from app.executive_controlled_reentry.service import executive_controlled_reentry_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_controlled_reentry_service.reset()


def payload(**observation_overrides):
    values = {
        "containment_state": "released",
        "account_risk_state": "account-risk-clear",
        "broker_session_ready": True,
        "market_data_ready": True,
        "positions_reconciled": True,
        "pending_orders_reconciled": True,
        "incident_review_completed": True,
        "root_cause_identified": True,
        "remediation_verified": True,
        "cooldown_elapsed_minutes": 60,
        "human_approval_verified": True,
        "canary_requested": True,
        "canary_dispatched": True,
        "canary_acknowledged": True,
        "canary_risk_pct": 0.25,
        "canary_orders": 1,
        "canary_failures": 0,
        "canary_slippage_bps": 5,
        "canary_reconciliation_complete": True,
    }
    values.update(observation_overrides)
    return ControlledReentryAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        containment_id=uuid4(),
        account_reference="prop-100k",
        broker_reference="broker-a",
        observation=ControlledReentryObservation(**values),
    )


def test_limited_trading_after_successful_canary() -> None:
    record = executive_controlled_reentry_service.assess(payload())
    assert record.state == ControlledReentryState.limited_trading
    assert record.new_orders_enabled is True
    assert record.full_trading_enabled is False


def test_containment_release_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(containment_state="contained"))
    assert record.state == ControlledReentryState.containment_release_required


def test_account_risk_clear_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(account_risk_state="daily-loss-breached"))
    assert record.state == ControlledReentryState.account_reconciliation_required


def test_broker_reconciliation_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(positions_reconciled=False))
    assert record.state == ControlledReentryState.account_reconciliation_required


def test_incident_remediation_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(remediation_verified=False))
    assert record.state == ControlledReentryState.readiness_required


def test_cooldown_active() -> None:
    record = executive_controlled_reentry_service.assess(payload(cooldown_elapsed_minutes=30))
    assert record.state == ControlledReentryState.cooldown_active


def test_human_approval_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(human_approval_verified=False))
    assert record.state == ControlledReentryState.approval_required


def test_canary_required() -> None:
    record = executive_controlled_reentry_service.assess(payload(canary_dispatched=False))
    assert record.state == ControlledReentryState.canary_required


def test_canary_failure() -> None:
    record = executive_controlled_reentry_service.assess(payload(canary_failures=1))
    assert record.state == ControlledReentryState.canary_failed
    assert record.new_orders_enabled is False


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    record = executive_controlled_reentry_service.assess(request)
    assert record.state == ControlledReentryState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_controlled_reentry_service.assess(request)
    with pytest.raises(ValueError):
        executive_controlled_reentry_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_controlled_reentry_service.assess(payload())
    assert executive_controlled_reentry_service.get(record.id, "other-workspace") is None


def test_record_canary_and_full_reenable() -> None:
    request = payload(canary_dispatched=False)
    record = executive_controlled_reentry_service.assess(request)
    limited = executive_controlled_reentry_service.record_canary(
        CanaryResultRequest(
            workspace_id=record.workspace_id,
            reentry_id=record.reentry_id,
            actor_id="master-brano",
            human_approval_verified=True,
            canary_orders=1,
            canary_failures=0,
            canary_slippage_bps=4,
            reconciliation_complete=True,
        )
    )
    assert limited.state == ControlledReentryState.limited_trading
    enabled = executive_controlled_reentry_service.full_reenable(
        FullReenableRequest(
            workspace_id=record.workspace_id,
            reentry_id=record.reentry_id,
            actor_id="master-brano",
            human_approval_verified=True,
        )
    )
    assert enabled.state == ControlledReentryState.trading_reenabled
    assert enabled.full_trading_enabled is True
