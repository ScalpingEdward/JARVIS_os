from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AcknowledgeCreate, AuditRecord, CoverageRecord, CoverageState, EscalationCreate,
    EscalationRecord, EscalationState, HandoverCreate, HandoverRecord, MetricsRecord,
    Mutation, OnCallStatus, ScheduleCreate, ScheduleRecord, ScheduleState,
)


class OnCallService:
    def __init__(self) -> None:
        self.schedules: dict[UUID, ScheduleRecord] = {}
        self.handovers: dict[UUID, HandoverRecord] = {}
        self.escalations: dict[UUID, EscalationRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            details=details,
        ))

    def status(self) -> OnCallStatus:
        return OnCallStatus(
            schedules=len(self.schedules),
            escalations=len(self.escalations),
            handovers=len(self.handovers),
        )

    def create_schedule(self, payload: ScheduleCreate) -> ScheduleRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id
            and item.schedule_key == payload.schedule_key
            and item.state != ScheduleState.RETIRED
            for item in self.schedules.values()
        )
        if duplicate:
            raise ValueError("active on-call schedule key already exists")
        item = ScheduleRecord(**payload.model_dump())
        self.schedules[item.id] = item
        self._audit(item.workspace_id, "schedule.created", "schedule", item.id, item.owner_id)
        return item

    def list_schedules(self, workspace_id: str, state: ScheduleState | None = None) -> list[ScheduleRecord]:
        return [
            item for item in self.schedules.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def get_schedule(self, schedule_id: UUID, workspace_id: str) -> ScheduleRecord | None:
        item = self.schedules.get(schedule_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_schedule_state(self, schedule_id: UUID, workspace_id: str, payload: Mutation, state: ScheduleState) -> ScheduleRecord | None:
        item = self.get_schedule(schedule_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        allowed = {
            ScheduleState.DRAFT: {ScheduleState.ACTIVE, ScheduleState.RETIRED},
            ScheduleState.ACTIVE: {ScheduleState.PAUSED, ScheduleState.RETIRED},
            ScheduleState.PAUSED: {ScheduleState.ACTIVE, ScheduleState.RETIRED},
            ScheduleState.RETIRED: set(),
        }
        if state not in allowed[item.state]:
            raise ValueError("invalid on-call schedule transition")
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"schedule.{state.value}", "schedule", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_handover(self, payload: HandoverCreate) -> HandoverRecord:
        schedule = self.get_schedule(payload.schedule_id, payload.workspace_id)
        if schedule is None or schedule.state != ScheduleState.ACTIVE:
            raise ValueError("active owned schedule is required")
        users = {member.user_id for member in schedule.rotation_members}
        if payload.requester_id != schedule.owner_id and payload.requester_id != payload.from_user_id:
            raise ValueError("handover requires owner or current responder")
        if payload.from_user_id not in users or payload.to_user_id not in users:
            raise ValueError("handover users must belong to the rotation")
        item = HandoverRecord(**payload.model_dump())
        self.handovers[item.id] = item
        self._audit(item.workspace_id, "handover.created", "handover", item.id, item.requester_id, schedule_id=str(item.schedule_id))
        return item

    def list_handovers(self, workspace_id: str, schedule_id: UUID | None = None) -> list[HandoverRecord]:
        return [
            item for item in self.handovers.values()
            if item.workspace_id == workspace_id and (schedule_id is None or item.schedule_id == schedule_id)
        ]

    def _rotation_user(self, schedule: ScheduleRecord, at: datetime) -> str:
        members = sorted(schedule.rotation_members, key=lambda item: item.position)
        elapsed = max(0, int((at - schedule.rotation_start).total_seconds()))
        index = (elapsed // schedule.shift_duration_seconds) % len(members)
        return members[index].user_id

    def coverage(self, workspace_id: str, schedule_id: UUID, at: datetime | None = None) -> CoverageRecord:
        schedule = self.get_schedule(schedule_id, workspace_id)
        if schedule is None:
            raise ValueError("schedule not found")
        evaluated_at = at or datetime.now(timezone.utc)
        active = [self._rotation_user(schedule, evaluated_at)] if schedule.state == ScheduleState.ACTIVE else []
        applicable = [
            handover for handover in self.handovers.values()
            if handover.workspace_id == workspace_id
            and handover.schedule_id == schedule_id
            and handover.start_at <= evaluated_at < handover.end_at
        ]
        for handover in applicable:
            if handover.from_user_id in active:
                active.remove(handover.from_user_id)
            if handover.to_user_id not in active:
                active.append(handover.to_user_id)
        if not active:
            state = CoverageState.GAP
        elif len(active) > 1:
            state = CoverageState.OVERLAP
        else:
            state = CoverageState.COVERED
        record = CoverageRecord(
            workspace_id=workspace_id,
            schedule_id=schedule_id,
            evaluated_at=evaluated_at,
            active_user_ids=active,
            state=state,
            handover_ids=[item.id for item in applicable],
        )
        self._audit(workspace_id, "coverage.evaluated", "schedule", schedule_id, "system", state=state.value)
        return record

    def create_escalation(self, payload: EscalationCreate) -> EscalationRecord:
        schedule = self.get_schedule(payload.schedule_id, payload.workspace_id)
        if schedule is None or schedule.state != ScheduleState.ACTIVE:
            raise ValueError("active on-call schedule is required")
        coverage = self.coverage(payload.workspace_id, payload.schedule_id)
        if coverage.state == CoverageState.GAP:
            raise ValueError("on-call coverage gap prevents escalation planning")
        first = schedule.escalation_levels[0]
        assigned = list(dict.fromkeys(coverage.active_user_ids + first.target_user_ids))
        item = EscalationRecord(
            **payload.model_dump(),
            assigned_user_ids=assigned,
            next_escalation_at=datetime.now(timezone.utc) + timedelta(seconds=first.acknowledge_within_seconds),
        )
        self.escalations[item.id] = item
        self._audit(item.workspace_id, "escalation.planned", "escalation", item.id, item.requester_id, assigned=assigned)
        return item

    def list_escalations(self, workspace_id: str, state: EscalationState | None = None) -> list[EscalationRecord]:
        return [
            item for item in self.escalations.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def mark_notified(self, escalation_id: UUID, workspace_id: str, payload: Mutation) -> EscalationRecord | None:
        item = self.escalations.get(escalation_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        if item.state != EscalationState.PLANNED:
            raise ValueError("only planned escalations can be marked notified")
        item.state = EscalationState.NOTIFIED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "escalation.notified", "escalation", item.id, payload.requester_id)
        return item

    def acknowledge(self, payload: AcknowledgeCreate) -> EscalationRecord:
        item = self.escalations.get(payload.escalation_id)
        if item is None or item.workspace_id != payload.workspace_id:
            raise ValueError("escalation not found")
        if payload.requester_id not in item.assigned_user_ids:
            raise ValueError("only assigned responders may acknowledge")
        if item.state not in {EscalationState.PLANNED, EscalationState.NOTIFIED, EscalationState.ESCALATED}:
            raise ValueError("escalation cannot be acknowledged in current state")
        item.state = EscalationState.ACKNOWLEDGED
        item.acknowledged_by = payload.requester_id
        item.acknowledged_at = datetime.now(timezone.utc)
        item.next_escalation_at = None
        item.updated_at = item.acknowledged_at
        self._audit(item.workspace_id, "escalation.acknowledged", "escalation", item.id, payload.requester_id, note=payload.note)
        return item

    def escalate_due(self, workspace_id: str, requester_id: str, evaluation_time: datetime | None = None) -> list[EscalationRecord]:
        now = evaluation_time or datetime.now(timezone.utc)
        changed: list[EscalationRecord] = []
        for item in self.escalations.values():
            if item.workspace_id != workspace_id or item.state not in {EscalationState.PLANNED, EscalationState.NOTIFIED, EscalationState.ESCALATED}:
                continue
            if item.next_escalation_at is None or item.next_escalation_at > now:
                continue
            schedule = self.schedules[item.schedule_id]
            next_level = item.current_level + 1
            if next_level > len(schedule.escalation_levels):
                item.next_escalation_at = None
                continue
            level = schedule.escalation_levels[next_level - 1]
            item.current_level = next_level
            item.state = EscalationState.ESCALATED
            item.assigned_user_ids = list(dict.fromkeys(item.assigned_user_ids + level.target_user_ids))
            item.next_escalation_at = now + timedelta(seconds=level.acknowledge_within_seconds)
            item.updated_at = now
            self._audit(workspace_id, "escalation.advanced", "escalation", item.id, requester_id, level=next_level)
            changed.append(item)
        return changed

    def resolve(self, escalation_id: UUID, workspace_id: str, payload: Mutation) -> EscalationRecord | None:
        item = self.escalations.get(escalation_id)
        if item is None or item.workspace_id != workspace_id:
            return None
        if payload.requester_id not in item.assigned_user_ids:
            return None
        if item.state not in {EscalationState.ACKNOWLEDGED, EscalationState.ESCALATED, EscalationState.NOTIFIED}:
            raise ValueError("escalation cannot be resolved in current state")
        item.state = EscalationState.RESOLVED
        item.next_escalation_at = None
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "escalation.resolved", "escalation", item.id, payload.requester_id, reason=payload.reason)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        schedules = self.list_schedules(workspace_id)
        escalations = self.list_escalations(workspace_id)
        gaps = 0
        for schedule in schedules:
            if self.coverage(workspace_id, schedule.id).state == CoverageState.GAP:
                gaps += 1
        return MetricsRecord(
            workspace_id=workspace_id,
            schedules=len(schedules),
            active_schedules=sum(item.state == ScheduleState.ACTIVE for item in schedules),
            planned_escalations=sum(item.state == EscalationState.PLANNED for item in escalations),
            acknowledged_escalations=sum(item.state == EscalationState.ACKNOWLEDGED for item in escalations),
            escalated_events=sum(item.current_level > 1 for item in escalations),
            unresolved_escalations=sum(item.state not in {EscalationState.RESOLVED, EscalationState.CANCELLED} for item in escalations),
            handovers=len(self.list_handovers(workspace_id)),
            coverage_gaps=gaps,
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


on_call_service = OnCallService()
