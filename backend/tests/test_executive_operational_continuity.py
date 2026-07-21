from uuid import uuid4

import pytest

from app.executive_operational_continuity.models import (
    ContinuityAssessmentCreate,
    ContinuityObservation,
    ContinuityState,
    FailoverRequest,
    RecoveryRequest,
)
from app.executive_operational_continuity.service import executive_operational_continuity_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_operational_continuity_service.reset()


def payload(**overrides) -> ContinuityAssessmentCreate:
    values = {"copy_execution_state": "synchronized"}
    values.update(overrides)
    return ContinuityAssessmentCreate(
        workspace_id="master-brano",
        source_key=str(uuid4()),
        actor_id="master-brano",
        copy_group_id=uuid4(),
        primary_node="vps-primary",
        standby_node="vps-standby",
        observation=ContinuityObservation(**values),
    )


def test_continuity_ready() -> None:
    record = executive_operational_continuity_service.assess(payload())
    assert record.state == ContinuityState.continuity_ready


def test_copy_sync_dependency() -> None:
    record = executive_operational_continuity_service.assess(payload(copy_execution_state="drift-detected"))
    assert record.state == ContinuityState.copy_sync_required


def test_standby_required() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False, standby_vps_ready=False))
    assert record.state == ContinuityState.health_degraded


def test_checkpoint_required() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False, state_checkpoint_current=False))
    assert record.state == ContinuityState.health_degraded


def test_failover_approval_required() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False))
    assert record.state == ContinuityState.failover_approval_required


def test_failover_pending() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False, human_approval_verified=True))
    assert record.state == ContinuityState.failover_pending


def test_failed_over() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False))
    changed = executive_operational_continuity_service.failover(FailoverRequest(
        workspace_id=record.workspace_id,
        continuity_id=record.continuity_id,
        actor_id="master-brano",
        human_approval_verified=True,
        active_node="vps-standby",
    ))
    assert changed.state == ContinuityState.failed_over
    assert changed.active_node == "vps-standby"


def test_reconciliation_required() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False))
    changed = executive_operational_continuity_service.failover(FailoverRequest(
        workspace_id=record.workspace_id,
        continuity_id=record.continuity_id,
        actor_id="master-brano",
        human_approval_verified=True,
        active_node="vps-standby",
        final_reconciliation_complete=False,
    ))
    assert changed.state == ContinuityState.reconciliation_required


def test_recovery() -> None:
    record = executive_operational_continuity_service.assess(payload(primary_vps_healthy=False))
    recovered = executive_operational_continuity_service.recover(RecoveryRequest(
        workspace_id=record.workspace_id,
        continuity_id=record.continuity_id,
        actor_id="master-brano",
        human_approval_verified=True,
        active_node="vps-primary",
    ))
    assert recovered.state == ContinuityState.recovered


def test_risk_brain_block() -> None:
    request = payload()
    request.risk_brain_clear = False
    assert executive_operational_continuity_service.assess(request).state == ContinuityState.blocked


def test_duplicate_source_key_rejected() -> None:
    request = payload()
    executive_operational_continuity_service.assess(request)
    with pytest.raises(ValueError):
        executive_operational_continuity_service.assess(request)


def test_workspace_isolation() -> None:
    record = executive_operational_continuity_service.assess(payload())
    assert executive_operational_continuity_service.get(record.id, "other-workspace") is None
