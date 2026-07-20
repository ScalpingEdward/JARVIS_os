from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TransactionalOutboxAssessment,
    TransactionalOutboxAssessmentCreate,
    TransactionalOutboxScores,
    TransactionalOutboxState,
    TransactionalOutboxStatusResponse,
)


class ExecutiveTransactionalOutboxService:
    def __init__(self) -> None:
        self._records: dict[UUID, TransactionalOutboxAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._outbox_ids: set[tuple[str, UUID]] = set()
        self._idempotency_keys: set[tuple[str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TransactionalOutboxAssessmentCreate) -> TransactionalOutboxAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        outbox_key = (payload.workspace_id, payload.outbox_record_id)
        inbox_key = (payload.workspace_id, payload.consumer_id, payload.idempotency_key)
        duplicate = source_key in self._source_keys or outbox_key in self._outbox_ids or inbox_key in self._idempotency_keys

        observation = payload.observation
        policy = payload.policy
        reasons: list[str] = []

        transaction_safe = (
            observation.business_commit_succeeded
            and observation.outbox_inserted_same_transaction
            and observation.transaction_id_verified
            and observation.event_persisted
        )
        lease_safe = (
            observation.publisher_lease_acquired
            and observation.lease_owner_verified
            and observation.lease_age_seconds <= policy.maximum_lease_age_seconds
        )
        publish_safe = (
            observation.publish_attempted
            and observation.broker_acknowledged
            and observation.published_marker_persisted
            and observation.publish_attempts <= policy.maximum_publish_attempts
            and observation.latency_ms <= policy.maximum_latency_ms
        )
        inbox_safe = (
            observation.inbox_record_persisted
            and observation.consumer_side_effect_committed
            and observation.consumer_ack_persisted
        )
        checkpoint_safe = observation.checkpoint_persisted
        stale = observation.age_seconds > policy.maximum_record_age_seconds
        lease_recoverable = observation.lease_expired and policy.allow_expired_lease_recovery
        recovery_needed = (
            observation.business_commit_succeeded
            and observation.event_persisted
            and not observation.published_marker_persisted
        ) or stale or lease_recoverable

        if not payload.risk_brain_clear:
            state, action = TransactionalOutboxState.blocked, "block-transactional-outbox"
            reasons.append("Risk Brain blocks outbox or inbox processing")
        elif payload.persistent_store_state not in {"store-ready", "dispatched"}:
            state, action = TransactionalOutboxState.blocked, "complete-persistent-event-store-governance"
            reasons.append("Persistent event store has not authorized transactional messaging")
        elif duplicate or observation.inbox_duplicate_detected:
            state, action = TransactionalOutboxState.duplicate, "discard-idempotent-duplicate"
            reasons.append("Duplicate outbox record or inbox idempotency key detected")
        elif policy.prohibit_raw_transaction_payload and observation.raw_transaction_payload_present:
            state, action = TransactionalOutboxState.blocked, "remove-raw-transaction-payload"
            reasons.append("Raw transactional payloads are prohibited")
        elif policy.require_same_transaction_write and not transaction_safe:
            state, action = TransactionalOutboxState.transaction_required, "repair-atomic-business-outbox-commit"
            reasons.append("Business mutation and outbox event were not verified in one transaction")
        elif policy.require_publisher_lease and not lease_safe:
            if lease_recoverable:
                state, action = TransactionalOutboxState.recovery_required, "recover-expired-publisher-lease"
                reasons.append("Publisher lease expired and requires bounded recovery")
            else:
                state, action = TransactionalOutboxState.lease_conflict, "resolve-publisher-lease-conflict"
                reasons.append("Publisher lease is missing, invalid or too old")
        elif recovery_needed and not observation.recovery_scan_completed:
            state, action = TransactionalOutboxState.recovery_required, "run-outbox-recovery-scan"
            reasons.append("Committed but unpublished outbox data requires recovery scanning")
        elif policy.require_broker_ack_before_mark_published and not publish_safe:
            state, action = TransactionalOutboxState.recovery_required, "retry-bounded-outbox-publication"
            reasons.append("Broker acknowledgement and published checkpoint are incomplete")
        elif policy.require_inbox_deduplication and not inbox_safe:
            state, action = TransactionalOutboxState.transaction_required, "complete-atomic-inbox-consumer-commit"
            reasons.append("Inbox deduplication and consumer side effect are not atomically persisted")
        elif policy.require_checkpoint_persistence and not checkpoint_safe:
            state, action = TransactionalOutboxState.recovery_required, "persist-publication-checkpoint"
            reasons.append("Publication checkpoint is missing")
        else:
            state, action = TransactionalOutboxState.checkpoint_ready, "accept-transactional-message-boundary"
            reasons.append("Outbox publication, inbox deduplication and checkpoints passed governance")

        dispatchable = state == TransactionalOutboxState.checkpoint_ready
        recoverable = state == TransactionalOutboxState.recovery_required
        if dispatchable:
            state = TransactionalOutboxState.dispatched
            action = "dispatch-checkpoint-to-v18-64"
            reasons.append("Transactional checkpoint is ready for persistent event-store delivery")

        transaction_score = 100 if transaction_safe else 0
        publication_score = 100 if lease_safe and publish_safe else 0
        inbox_score = 100 if inbox_safe and not observation.inbox_duplicate_detected else 0
        recovery_score = 100 if observation.recovery_scan_completed or not recovery_needed else 0
        checkpoint_score = 100 if checkpoint_safe else 0
        confidence = round((transaction_score + publication_score + inbox_score + recovery_score + checkpoint_score) / 5)

        record = TransactionalOutboxAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            outbox_record_id=payload.outbox_record_id,
            event_id=payload.event_id,
            transaction_id=payload.transaction_id,
            aggregate_id=payload.aggregate_id,
            publisher_id=payload.publisher_id,
            consumer_id=payload.consumer_id,
            state=state,
            dispatchable=dispatchable,
            recoverable=recoverable,
            target_module="executive-persistent-event-store" if dispatchable else None,
            recommended_action=action,
            scores=TransactionalOutboxScores(
                transaction_integrity=transaction_score,
                publication_safety=publication_score,
                inbox_integrity=inbox_score,
                recovery_readiness=recovery_score,
                checkpoint_quality=checkpoint_score,
                outbox_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._outbox_ids.add(outbox_key)
        self._idempotency_keys.add(inbox_key)
        self._audit.append(AuditRecord(
            workspace_id=payload.workspace_id,
            assessment_id=record.id,
            event_id=payload.event_id,
            actor_id=payload.actor_id,
            action=action,
        ))
        return record

    def get(self, assessment_id: UUID, workspace_id: str) -> TransactionalOutboxAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_assessments(self, workspace_id: str) -> list[TransactionalOutboxAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> TransactionalOutboxStatusResponse:
        items = self.list_assessments(workspace_id)
        return TransactionalOutboxStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            dispatched=sum(item.state == TransactionalOutboxState.dispatched for item in items),
            recovery_required=sum(item.state == TransactionalOutboxState.recovery_required for item in items),
            latest_state=items[-1].state if items else None,
        )


executive_transactional_outbox_service = ExecutiveTransactionalOutboxService()
