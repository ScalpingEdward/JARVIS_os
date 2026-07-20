from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    EventBusAssessment,
    EventBusAssessmentCreate,
    EventBusScores,
    EventBusState,
    EventBusStatusResponse,
    RetryClass,
)


class ExecutiveEventBusService:
    def __init__(self) -> None:
        self._records: dict[UUID, EventBusAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._event_ids: set[tuple[str, UUID]] = set()
        self._idempotency_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: EventBusAssessmentCreate) -> EventBusAssessment:
        envelope = payload.envelope
        if envelope.workspace_id != payload.workspace_id:
            raise ValueError("Envelope workspace does not match assessment workspace")

        source_key = (payload.workspace_id, payload.source_key)
        event_key = (payload.workspace_id, envelope.event_id)
        idempotency_key = (payload.workspace_id, envelope.idempotency_key)
        duplicate = source_key in self._source_keys or event_key in self._event_ids or idempotency_key in self._idempotency_keys

        observation = payload.observation
        policy = payload.policy
        reasons: list[str] = []
        traceable = bool(envelope.correlation_id and envelope.trace_id)
        ordering_ok = not observation.ordering_violation
        if envelope.sequence_number is not None and payload.previous_sequence_number is not None:
            ordering_ok = ordering_ok and envelope.sequence_number == payload.previous_sequence_number + 1

        replay_requested = envelope.replay_of_event_id is not None
        replay_authorized = (
            replay_requested
            and policy.allow_replay
            and (payload.human_replay_approved or not policy.require_human_replay_approval)
        )

        if observation.rate_limited:
            retry_class = RetryClass.rate_limited
        elif not observation.dependency_available or observation.timed_out:
            retry_class = RetryClass.dependency_unavailable if not observation.dependency_available else RetryClass.transient
        elif observation.consumer_rejected or not observation.schema_valid or not observation.target_registered:
            retry_class = RetryClass.permanent
        else:
            retry_class = RetryClass.none

        if not payload.risk_brain_clear:
            state, action = EventBusState.blocked, "block-event-dispatch"
            reasons.append("Risk Brain blocks event-bus activity")
        elif duplicate:
            state, action = EventBusState.duplicate, "discard-duplicate-event"
            reasons.append("Duplicate source key, event ID or idempotency key detected")
        elif policy.require_schema_validation and not observation.schema_valid:
            state, action = EventBusState.schema_rejected, "reject-invalid-event-schema"
            reasons.append("Event payload failed schema validation")
        elif policy.require_registered_target and not observation.target_registered:
            state, action = EventBusState.schema_rejected, "reject-unregistered-target"
            reasons.append("Target module is not registered")
        elif (policy.require_correlation_id or policy.require_trace_id) and not traceable:
            state, action = EventBusState.schema_rejected, "repair-event-trace-context"
            reasons.append("Correlation or trace context is missing")
        elif policy.enforce_ordering and not ordering_ok:
            state, action = EventBusState.blocked, "quarantine-ordering-violation"
            reasons.append("Event ordering contract was violated")
        elif replay_requested and not replay_authorized:
            state, action = EventBusState.blocked, "require-human-replay-approval"
            reasons.append("Replay requires explicit policy and human approval")
        elif observation.consumer_acknowledged:
            state, action = EventBusState.accepted, "accept-consumer-acknowledgement"
            reasons.append("Consumer acknowledged the event")
        elif retry_class in {RetryClass.transient, RetryClass.rate_limited, RetryClass.dependency_unavailable} and policy.retry_transient_failures and observation.attempts < policy.maximum_attempts:
            state, action = EventBusState.retry_scheduled, "schedule-bounded-event-retry"
            reasons.append("Transient delivery failure has retry budget remaining")
        elif retry_class == RetryClass.permanent or observation.attempts >= policy.maximum_attempts:
            state, action = EventBusState.dead_lettered, "route-event-to-dead-letter"
            reasons.append("Event failed permanently or exhausted its retry budget")
        else:
            state, action = EventBusState.accepted, "accept-event-for-dispatch"
            reasons.append("Event passed envelope, schema, trace and ordering governance")

        dispatchable = state == EventBusState.accepted and not observation.consumer_acknowledged
        if dispatchable:
            state = EventBusState.replay_authorized if replay_authorized else EventBusState.dispatched
            action = "dispatch-governed-event"
            reasons.append("Governed event is ready for target-module dispatch")

        dead_lettered = state == EventBusState.dead_lettered
        replayable = dead_lettered and policy.allow_replay
        envelope_score = 100 if envelope.event_type and envelope.payload_schema and envelope.idempotency_key else 0
        schema_score = 100 if observation.schema_valid and observation.target_registered else 0
        trace_score = 100 if traceable else 0
        delivery_score = 100 if observation.consumer_acknowledged else max(0, 100 - observation.attempts * 15)
        ordering_score = 100 if ordering_ok else 0
        confidence = round((envelope_score + schema_score + trace_score + delivery_score + ordering_score) / 5)

        record = EventBusAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            envelope=envelope,
            state=state,
            retry_class=retry_class,
            dispatchable=dispatchable,
            replayable=replayable,
            dead_lettered=dead_lettered,
            recommended_action=action,
            scores=EventBusScores(
                envelope_integrity=envelope_score,
                schema_quality=schema_score,
                traceability=trace_score,
                delivery_reliability=delivery_score,
                ordering_safety=ordering_score,
                bus_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._event_ids.add(event_key)
        self._idempotency_keys.add(idempotency_key)
        self._audit.append(AuditRecord(
            workspace_id=payload.workspace_id,
            assessment_id=record.id,
            event_id=envelope.event_id,
            actor_id=payload.actor_id,
            action=action,
        ))
        return record

    def status(self, workspace_id: str) -> EventBusStatusResponse:
        items = self.list_assessments(workspace_id)
        return EventBusStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            dispatched=sum(item.state in {EventBusState.dispatched, EventBusState.replay_authorized} for item in items),
            dead_letters=sum(item.dead_lettered for item in items),
            latest_state=items[-1].state if items else None,
        )

    def list_assessments(self, workspace_id: str) -> list[EventBusAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> EventBusAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_event_bus_service = ExecutiveEventBusService()
