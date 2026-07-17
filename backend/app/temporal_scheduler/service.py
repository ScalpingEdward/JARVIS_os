from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import (
    AuditRecord, ManualTriggerRequest, MisfirePolicy, Mutation, RunRecord, RunState,
    ScheduleCreate, ScheduleRecord, ScheduleState, SchedulerMetrics, SchedulerStatus,
    TickRequest, TriggerKind,
)


class TemporalSchedulerService:
    def __init__(self) -> None:
        self.schedules: dict[UUID, ScheduleRecord] = {}
        self.runs: dict[UUID, RunRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _timezone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown timezone") from exc

    @staticmethod
    def _cron_field_matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
        if expression == "*":
            return True
        if expression.startswith("*/"):
            step = int(expression[2:])
            return step > 0 and value % step == 0
        values = {int(part) for part in expression.split(",")}
        if any(item < minimum or item > maximum for item in values):
            raise ValueError("cron field is outside supported range")
        return value in values

    def _validate_cron(self, expression: str) -> None:
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("cron_expression must contain five fields")
        checks = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
        for part, (minimum, maximum) in zip(parts, checks):
            self._cron_field_matches(minimum, part, minimum, maximum)

    def _next_cron(self, schedule: ScheduleRecord, after: datetime) -> datetime | None:
        parts = (schedule.cron_expression or "").split()
        local = self._utc(after).astimezone(self._timezone(schedule.timezone_name)).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(527040):
            weekday = (local.weekday() + 1) % 7
            if (
                self._cron_field_matches(local.minute, parts[0], 0, 59)
                and self._cron_field_matches(local.hour, parts[1], 0, 23)
                and self._cron_field_matches(local.day, parts[2], 1, 31)
                and self._cron_field_matches(local.month, parts[3], 1, 12)
                and self._cron_field_matches(weekday, parts[4], 0, 6)
            ):
                return local.astimezone(timezone.utc)
            local += timedelta(minutes=1)
        return None

    def _within_calendar(self, schedule: ScheduleRecord, candidate: datetime) -> bool:
        local = self._utc(candidate).astimezone(self._timezone(schedule.timezone_name))
        if schedule.allowed_weekdays and local.weekday() not in schedule.allowed_weekdays:
            return False
        if schedule.window_start and schedule.window_end:
            current = local.timetz().replace(tzinfo=None)
            if schedule.window_start <= schedule.window_end:
                if not schedule.window_start <= current <= schedule.window_end:
                    return False
            elif not (current >= schedule.window_start or current <= schedule.window_end):
                return False
        if schedule.start_at and self._utc(candidate) < self._utc(schedule.start_at):
            return False
        if schedule.end_at and self._utc(candidate) > self._utc(schedule.end_at):
            return False
        return True

    def _next_after(self, schedule: ScheduleRecord, after: datetime) -> datetime | None:
        after = self._utc(after)
        if schedule.trigger_kind == TriggerKind.ONCE:
            candidate = self._utc(schedule.run_at) if schedule.run_at else None
            return candidate if candidate and candidate > after and self._within_calendar(schedule, candidate) else None
        if schedule.trigger_kind == TriggerKind.INTERVAL:
            base = self._utc(schedule.start_at or schedule.created_at)
            seconds = schedule.interval_seconds or 60
            if after < base:
                candidate = base
            else:
                elapsed = int((after - base).total_seconds())
                candidate = base + timedelta(seconds=((elapsed // seconds) + 1) * seconds)
            for _ in range(10000):
                if schedule.end_at and candidate > self._utc(schedule.end_at):
                    return None
                if self._within_calendar(schedule, candidate):
                    return candidate
                candidate += timedelta(seconds=seconds)
            return None
        candidate = self._next_cron(schedule, after)
        for _ in range(10000):
            if candidate is None or (schedule.end_at and candidate > self._utc(schedule.end_at)):
                return None
            if self._within_calendar(schedule, candidate):
                return candidate
            candidate = self._next_cron(schedule, candidate)
        return None

    def status(self) -> SchedulerStatus:
        return SchedulerStatus(
            schedules=len(self.schedules),
            runs=len(self.runs),
            active_schedules=sum(s.state == ScheduleState.ACTIVE for s in self.schedules.values()),
        )

    def create_schedule(self, payload: ScheduleCreate) -> ScheduleRecord:
        self._timezone(payload.timezone_name)
        if payload.trigger_kind == TriggerKind.CRON:
            self._validate_cron(payload.cron_expression or "")
        if any(s.workspace_id == payload.workspace_id and s.schedule_key == payload.schedule_key and s.state != ScheduleState.RETIRED for s in self.schedules.values()):
            raise ValueError("active schedule key already exists")
        data = payload.model_dump(exclude={"human_approved", "automatic_activation", "execute_target", "external_scheduler"})
        item = ScheduleRecord(**data)
        self.schedules[item.id] = item
        self._audit(item.workspace_id, "schedule.created", "schedule", item.id, item.owner_id)
        return item

    def list_schedules(self, workspace_id: str) -> list[ScheduleRecord]:
        return [s for s in self.schedules.values() if s.workspace_id == workspace_id]

    def get_schedule(self, schedule_id: UUID, workspace_id: str) -> ScheduleRecord | None:
        item = self.schedules.get(schedule_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_state(self, schedule_id: UUID, workspace_id: str, payload: Mutation, state: ScheduleState) -> ScheduleRecord | None:
        item = self.schedules.get(schedule_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if state == ScheduleState.ACTIVE:
            item.next_run_at = self._next_after(item, datetime.now(timezone.utc) - timedelta(microseconds=1))
            if item.next_run_at is None:
                raise ValueError("schedule has no future eligible run")
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"schedule.{state.value}", "schedule", item.id, payload.requester_id, reason=payload.reason)
        return item

    def _plan_run(self, schedule: ScheduleRecord, planned_for: datetime, source: str, reason: str = "") -> RunRecord:
        run = RunRecord(
            workspace_id=schedule.workspace_id,
            schedule_id=schedule.id,
            planned_for=self._utc(planned_for),
            trigger_source=source,
            target_type=schedule.target_type,
            target_reference=schedule.target_reference,
            payload=schedule.payload,
            correlation_id=f"schedule:{schedule.id}:{uuid4()}",
            reason=reason,
        )
        self.runs[run.id] = run
        return run

    def tick(self, payload: TickRequest) -> list[RunRecord]:
        now = self._utc(payload.evaluation_time or datetime.now(timezone.utc))
        planned: list[RunRecord] = []
        for schedule in self.schedules.values():
            if schedule.workspace_id != payload.workspace_id or schedule.state != ScheduleState.ACTIVE or not schedule.next_run_at:
                continue
            due = self._utc(schedule.next_run_at)
            if due > now:
                continue
            if (
                schedule.trigger_kind != TriggerKind.ONCE
                and schedule.misfire_policy == MisfirePolicy.SKIP
                and due < now
            ):
                run = self._plan_run(schedule, due, "misfire", "missed occurrence skipped")
                run.state = RunState.SKIPPED
                planned.append(run)
                schedule.next_run_at = self._next_after(schedule, now)
            elif schedule.misfire_policy == MisfirePolicy.CATCH_UP_PLAN:
                count = 0
                while due <= now and count < schedule.max_catch_up_runs:
                    planned.append(self._plan_run(schedule, due, "catch-up"))
                    count += 1
                    next_due = self._next_after(schedule, due)
                    if next_due is None:
                        break
                    due = next_due
                schedule.next_run_at = due if due > now else self._next_after(schedule, now)
            else:
                planned.append(self._plan_run(schedule, due, "schedule"))
                schedule.next_run_at = self._next_after(schedule, now)
            schedule.last_run_at = now
            schedule.run_count += len([r for r in planned if r.schedule_id == schedule.id])
            schedule.updated_at = now
            if schedule.trigger_kind == TriggerKind.ONCE or schedule.next_run_at is None:
                schedule.state = ScheduleState.PAUSED
            self._audit(schedule.workspace_id, "schedule.evaluated", "schedule", schedule.id, payload.requester_id, planned_runs=len([r for r in planned if r.schedule_id == schedule.id]))
        return planned

    def manual_trigger(self, schedule_id: UUID, payload: ManualTriggerRequest) -> RunRecord | None:
        item = self.schedules.get(schedule_id)
        if not item or item.workspace_id != payload.workspace_id or item.owner_id != payload.requester_id or item.state == ScheduleState.RETIRED:
            return None
        run = self._plan_run(item, datetime.now(timezone.utc), "manual", payload.reason)
        self._audit(item.workspace_id, "run.manual-planned", "run", run.id, payload.requester_id, schedule_id=str(item.id))
        return run

    def list_runs(self, workspace_id: str, schedule_id: UUID | None = None) -> list[RunRecord]:
        return [r for r in self.runs.values() if r.workspace_id == workspace_id and (schedule_id is None or r.schedule_id == schedule_id)]

    def set_run_state(self, run_id: UUID, workspace_id: str, payload: Mutation, state: RunState) -> RunRecord | None:
        run = self.runs.get(run_id)
        schedule = self.schedules.get(run.schedule_id) if run else None
        if not run or run.workspace_id != workspace_id or not schedule or schedule.owner_id != payload.requester_id:
            return None
        allowed = {
            RunState.RELEASED: {RunState.PLANNED},
            RunState.SUCCEEDED: {RunState.RELEASED},
            RunState.FAILED: {RunState.RELEASED},
            RunState.CANCELLED: {RunState.PLANNED},
        }
        if run.state not in allowed.get(state, set()):
            return None
        run.state = state
        run.reason = payload.reason or run.reason
        run.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"run.{state.value}", "run", run.id, payload.requester_id)
        return run

    def metrics(self, workspace_id: str) -> SchedulerMetrics:
        schedules = [s for s in self.schedules.values() if s.workspace_id == workspace_id]
        runs = [r for r in self.runs.values() if r.workspace_id == workspace_id]
        return SchedulerMetrics(
            workspace_id=workspace_id,
            schedules=len(schedules),
            active_schedules=sum(s.state == ScheduleState.ACTIVE for s in schedules),
            paused_schedules=sum(s.state == ScheduleState.PAUSED for s in schedules),
            planned_runs=sum(r.state in {RunState.PLANNED, RunState.RELEASED} for r in runs),
            skipped_runs=sum(r.state == RunState.SKIPPED for r in runs),
            completed_runs=sum(r.state == RunState.SUCCEEDED for r in runs),
            failed_runs=sum(r.state == RunState.FAILED for r in runs),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]


temporal_scheduler_service = TemporalSchedulerService()
