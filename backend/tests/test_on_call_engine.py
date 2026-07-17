from datetime import datetime, timedelta, timezone

import pytest

from app.on_call_engine.models import (
    AcknowledgeCreate, CoverageState, EscalationCreate, EscalationLevel,
    EscalationState, HandoverCreate, Mutation, RotationMember, ScheduleCreate,
    ScheduleState,
)
from app.on_call_engine.service import OnCallService


def _schedule(workspace: str = "alpha", owner: str = "owner", **overrides) -> ScheduleCreate:
    data = dict(
        workspace_id=workspace,
        owner_id=owner,
        schedule_key=f"primary-{workspace}",
        name="Primary operations on-call",
        service_keys=["event-bus", "job-orchestrator"],
        timezone_name="UTC",
        rotation_members=[
            RotationMember(user_id="alice", position=0),
            RotationMember(user_id="bob", position=1),
            RotationMember(user_id="manager", position=2, role="manager"),
        ],
        shift_duration_seconds=3600,
        rotation_start=datetime.now(timezone.utc) - timedelta(minutes=10),
        escalation_levels=[
            EscalationLevel(level=1, target_user_ids=["alice"], acknowledge_within_seconds=60),
            EscalationLevel(level=2, target_user_ids=["bob"], acknowledge_within_seconds=120),
            EscalationLevel(level=3, target_user_ids=["manager"], acknowledge_within_seconds=300),
        ],
    )
    data.update(overrides)
    return ScheduleCreate(**data)


def _active(service: OnCallService):
    schedule = service.create_schedule(_schedule())
    service.set_schedule_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    return schedule


def test_schedule_lifecycle_coverage_and_workspace_isolation() -> None:
    service = OnCallService()
    schedule = _active(service)
    assert schedule.state == ScheduleState.ACTIVE
    coverage = service.coverage("alpha", schedule.id)
    assert coverage.state == CoverageState.COVERED
    assert len(coverage.active_user_ids) == 1
    assert service.get_schedule(schedule.id, "beta") is None
    assert service.metrics("alpha").active_schedules == 1


def test_handover_replaces_current_responder() -> None:
    service = OnCallService()
    schedule = _active(service)
    before = service.coverage("alpha", schedule.id)
    current = before.active_user_ids[0]
    replacement = "bob" if current != "bob" else "alice"
    now = datetime.now(timezone.utc)
    handover = service.create_handover(HandoverCreate(
        workspace_id="alpha",
        requester_id=current,
        schedule_id=schedule.id,
        from_user_id=current,
        to_user_id=replacement,
        start_at=now - timedelta(minutes=1),
        end_at=now + timedelta(hours=1),
        reason="approved substitution",
    ))
    after = service.coverage("alpha", schedule.id, now)
    assert after.active_user_ids == [replacement]
    assert handover.id in after.handover_ids


def test_escalation_acknowledgement_and_resolution() -> None:
    service = OnCallService()
    schedule = _active(service)
    escalation = service.create_escalation(EscalationCreate(
        workspace_id="alpha",
        requester_id="owner",
        schedule_id=schedule.id,
        subject="Event bus degradation",
        correlation_id="corr-1",
    ))
    assert escalation.state == EscalationState.PLANNED
    responder = escalation.assigned_user_ids[0]
    acknowledged = service.acknowledge(AcknowledgeCreate(
        workspace_id="alpha",
        requester_id=responder,
        escalation_id=escalation.id,
        note="Taking ownership",
    ))
    assert acknowledged.state == EscalationState.ACKNOWLEDGED
    resolved = service.resolve(escalation.id, "alpha", Mutation(requester_id=responder, reason="service stable"))
    assert resolved is not None and resolved.state == EscalationState.RESOLVED


def test_due_escalation_advances_level_without_external_page() -> None:
    service = OnCallService()
    schedule = _active(service)
    escalation = service.create_escalation(EscalationCreate(
        workspace_id="alpha", requester_id="owner", schedule_id=schedule.id,
        subject="Queue latency", correlation_id="corr-2",
    ))
    due = escalation.next_escalation_at + timedelta(seconds=1)
    changed = service.escalate_due("alpha", "owner", due)
    assert changed[0].current_level == 2
    assert changed[0].state == EscalationState.ESCALATED
    assert "bob" in changed[0].assigned_user_ids


def test_permissions_validation_and_safety_guards() -> None:
    service = OnCallService()
    schedule = _active(service)
    escalation = service.create_escalation(EscalationCreate(
        workspace_id="alpha", requester_id="owner", schedule_id=schedule.id,
        subject="Worker failure", correlation_id="corr-3",
    ))
    with pytest.raises(ValueError, match="assigned responders"):
        service.acknowledge(AcknowledgeCreate(
            workspace_id="alpha", requester_id="outsider", escalation_id=escalation.id,
        ))
    with pytest.raises(ValueError, match="automatic on-call schedule activation"):
        ScheduleCreate(**{**_schedule().model_dump(), "automatic_activation": True})
    with pytest.raises(ValueError, match="automatic external paging"):
        ScheduleCreate(**{**_schedule().model_dump(), "notify_external": True})
    with pytest.raises(ValueError, match="never execute response actions"):
        ScheduleCreate(**{**_schedule().model_dump(), "execute_response": True})
    with pytest.raises(ValueError, match="external on-call providers"):
        ScheduleCreate(**{**_schedule().model_dump(), "external_provider": True})
