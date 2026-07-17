from datetime import datetime, timedelta, timezone

import pytest

from app.temporal_scheduler.models import (
    ManualTriggerRequest, MisfirePolicy, Mutation, RunState, ScheduleCreate,
    ScheduleState, TickRequest, TriggerKind,
)
from app.temporal_scheduler.service import TemporalSchedulerService


def _once(workspace: str = "alpha", owner: str = "owner", seconds: int = 60) -> ScheduleCreate:
    return ScheduleCreate(
        workspace_id=workspace,
        owner_id=owner,
        schedule_key=f"once-{workspace}",
        name="One-time plan",
        trigger_kind=TriggerKind.ONCE,
        run_at=datetime.now(timezone.utc) + timedelta(seconds=seconds),
        target_type="job",
        target_reference="queue/report",
    )


def test_once_schedule_activation_tick_and_run_lifecycle() -> None:
    service = TemporalSchedulerService()
    schedule = service.create_schedule(_once(seconds=5))
    assert schedule.state == ScheduleState.DRAFT

    active = service.set_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    assert active is not None and active.next_run_at is not None

    runs = service.tick(TickRequest(
        workspace_id="alpha",
        requester_id="owner",
        evaluation_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    ))
    assert len(runs) == 1
    assert runs[0].state == RunState.PLANNED
    assert schedule.state == ScheduleState.PAUSED

    released = service.set_run_state(runs[0].id, "alpha", Mutation(requester_id="owner"), RunState.RELEASED)
    assert released is not None and released.state == RunState.RELEASED
    succeeded = service.set_run_state(runs[0].id, "alpha", Mutation(requester_id="owner"), RunState.SUCCEEDED)
    assert succeeded is not None and succeeded.state == RunState.SUCCEEDED


def test_interval_priority_calendar_and_catch_up_planning() -> None:
    service = TemporalSchedulerService()
    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    schedule = service.create_schedule(ScheduleCreate(
        workspace_id="alpha",
        owner_id="owner",
        schedule_key="interval-report",
        name="Interval report",
        trigger_kind=TriggerKind.INTERVAL,
        interval_seconds=60,
        start_at=start,
        misfire_policy=MisfirePolicy.CATCH_UP_PLAN,
        max_catch_up_runs=3,
        target_type="job",
        target_reference="queue/report",
    ))
    service.set_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    schedule.next_run_at = start

    runs = service.tick(TickRequest(workspace_id="alpha", requester_id="owner"))
    assert len(runs) == 3
    assert all(run.trigger_source == "catch-up" for run in runs)
    assert schedule.next_run_at is not None


def test_cron_validation_timezone_manual_trigger_and_isolation() -> None:
    service = TemporalSchedulerService()
    cron = service.create_schedule(ScheduleCreate(
        workspace_id="alpha",
        owner_id="owner",
        schedule_key="weekday-cron",
        name="Weekday cron",
        trigger_kind=TriggerKind.CRON,
        cron_expression="*/15 8,9 * * 1,2,3,4,5",
        timezone_name="Europe/Berlin",
        target_type="workflow",
        target_reference="workflow/morning",
    ))
    active = service.set_state(cron.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    assert active is not None and active.next_run_at is not None
    assert service.get_schedule(cron.id, "beta") is None

    run = service.manual_trigger(cron.id, ManualTriggerRequest(
        workspace_id="alpha", requester_id="owner", reason="approved test",
    ))
    assert run is not None and run.trigger_source == "manual"
    assert service.manual_trigger(cron.id, ManualTriggerRequest(
        workspace_id="beta", requester_id="owner", reason="wrong workspace",
    )) is None

    with pytest.raises(ValueError, match="five fields"):
        service.create_schedule(ScheduleCreate(
            workspace_id="alpha",
            owner_id="owner",
            schedule_key="bad-cron",
            name="Bad cron",
            trigger_kind=TriggerKind.CRON,
            cron_expression="* * *",
            target_type="job",
            target_reference="queue/test",
        ))


def test_pause_resume_metrics_and_safety_guards() -> None:
    service = TemporalSchedulerService()
    schedule = service.create_schedule(_once(seconds=3600))
    service.set_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    paused = service.set_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.PAUSED)
    assert paused is not None and paused.state == ScheduleState.PAUSED
    resumed = service.set_state(schedule.id, "alpha", Mutation(requester_id="owner"), ScheduleState.ACTIVE)
    assert resumed is not None and resumed.state == ScheduleState.ACTIVE
    assert service.metrics("alpha").active_schedules == 1

    with pytest.raises(ValueError, match="automatic schedule activation"):
        _once().model_copy(update={"automatic_activation": True}).model_validate(
            _once().model_copy(update={"automatic_activation": True}).model_dump()
        )
    with pytest.raises(ValueError, match="never executes target actions"):
        TickRequest(workspace_id="alpha", requester_id="owner", execute_targets=True)
    with pytest.raises(ValueError, match="external scheduler providers"):
        ScheduleCreate(**{**_once().model_dump(), "external_scheduler": True})
