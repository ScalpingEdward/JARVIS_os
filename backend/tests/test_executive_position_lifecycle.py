from uuid import uuid4

import pytest

from app.executive_position_lifecycle.models import PositionLifecycleAssessmentCreate, PositionLifecycleObservation, PositionLifecycleState, PositionSide
from app.executive_position_lifecycle.service import executive_position_lifecycle_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_position_lifecycle_service.reset()


def payload(**observation_overrides):
    observation = PositionLifecycleObservation(**observation_overrides)
    return PositionLifecycleAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="human-operator",
        execution_id=uuid4(),
        broker_position_id=str(uuid4()),
        account_reference="paper-001",
        canonical_symbol="XAUUSD",
        side=PositionSide.buy,
        opened_quantity=0.1,
        observation=observation,
    )


def test_open_position_is_protected_and_reconciled() -> None:
    record = executive_position_lifecycle_service.assess(payload())
    assert record.state == PositionLifecycleState.position_open
    assert record.protected is True
    assert record.reconciled is True


def test_execution_dependency_is_required() -> None:
    record = executive_position_lifecycle_service.assess(payload(execution_state="partial-fill"))
    assert record.state == PositionLifecycleState.execution_required


def test_missing_stop_loss_requires_protection() -> None:
    record = executive_position_lifecycle_service.assess(payload(stop_loss_present=False))
    assert record.state == PositionLifecycleState.protection_required


def test_broker_mismatch_is_quarantined() -> None:
    record = executive_position_lifecycle_service.assess(payload(broker_quantity_matches=False))
    assert record.state == PositionLifecycleState.broker_mismatch


def test_modification_requires_human_approval() -> None:
    record = executive_position_lifecycle_service.assess(payload(modification_requested=True, modification_human_approved=False))
    assert record.state == PositionLifecycleState.modification_approval_required


def test_close_requires_human_approval() -> None:
    record = executive_position_lifecycle_service.assess(payload(close_requested=True, close_human_approved=False))
    assert record.state == PositionLifecycleState.modification_approval_required


def test_completed_close_is_reconciled() -> None:
    record = executive_position_lifecycle_service.assess(payload(close_requested=True, close_human_approved=True))
    assert record.state == PositionLifecycleState.position_closed
    assert record.closed is True


def test_risk_brain_blocks_position_lifecycle() -> None:
    request = payload()
    request.risk_brain_clear = False
    record = executive_position_lifecycle_service.assess(request)
    assert record.state == PositionLifecycleState.blocked


def test_duplicate_position_is_rejected() -> None:
    request = payload()
    executive_position_lifecycle_service.assess(request)
    request.source_key = str(uuid4())
    request.broker_position_id = str(uuid4())
    with pytest.raises(ValueError, match="Duplicate position ID"):
        executive_position_lifecycle_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_position_lifecycle_service.assess(payload())
    assert executive_position_lifecycle_service.get(record.id, "other-workspace") is None
