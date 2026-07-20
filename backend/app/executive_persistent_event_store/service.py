from __future__ import annotations

from uuid import UUID

from .models import (
    AckMode,
    AuditRecord,
    DeliveryGuarantee,
    PersistentEventStoreAssessment,
    PersistentEventStoreAssessmentCreate,
    PersistentEventStoreScores,
    PersistentEventStoreState,
    PersistentEventStoreStatusResponse,
)


class ExecutivePersistentEventStoreService:
    def __init__(self) -> None:
        self._records: dict[UUID, PersistentEventStoreAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._store_keys: set[tuple[str, str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: PersistentEventStoreAssessmentCreate) -> PersistentEventStoreAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        store_key = (
            payload.workspace_id,
            payload.adapter_id,
            payload.stream_name,
            payload.consumer_group,
        )
        if source_key in self._source_keys:
            raise ValueError("Duplicate persistent event-store source key")
        if store_key in self._store_keys:
            raise ValueError("Duplicate broker adapter, stream and consumer-group assessment")

        observation = payload.observation
        offset = payload.offset
        policy = payload.policy
        reasons: list[str] = []

        broker_allowed = payload.broker_type in policy.allowed_brokers
        dependency_ready = (
            observation.dependency_installed
            and observation.import_verified
            and observation.adapter_factory_verified
        )
        persistence_ready = (
            observation.connection_verified
            and observation.stream_or_topic_exists
            and observation.persistence_verified
            and observation.consumer_group_verified
            and observation.offset_store_verified
        )
        credentials_safe = (
            observation.authentication_reference_resolved
            and not observation.raw_credentials_present
            and observation.encryption_in_transit_verified
        )
        latency_safe = observation.latency_ms <= policy.maximum_latency_ms
        replication_safe = observation.replication_factor >= policy.minimum_replication_factor
        retention_safe = (
            policy.retention_hours_minimum
            <= payload.retention_hours
            <= policy.retention_hours_maximum
        )
        ack_safe = (
            not policy.require_manual_or_transactional_ack
            or payload.ack_mode in {AckMode.manual, AckMode.transactional}
        )
        effectively_once_safe = (
            payload.delivery_guarantee != DeliveryGuarantee.effectively_once
            or (
                observation.idempotent_producer_verified
                and observation.transactional_commit_verified
                and payload.ack_mode == AckMode.transactional
            )
        )
        guarantee_safe = (
            payload.delivery_guarantee == policy.required_delivery_guarantee
            or payload.delivery_guarantee == DeliveryGuarantee.effectively_once
        )
        consumer_lag = max(0, offset.high_watermark - offset.observed_offset)
        offset_safe = (
            not offset.offset_regression_detected
            and offset.observed_offset >= max(offset.committed_offset, 0)
            and offset.observed_offset <= offset.high_watermark
            and consumer_lag <= policy.maximum_consumer_lag
        )

        if not payload.risk_brain_clear:
            state, action = PersistentEventStoreState.blocked, "block-persistent-event-store"
            reasons.append("Risk Brain blocks persistent event-store activity")
        elif payload.event_bus_state not in {"accepted", "dispatched", "replay-authorized"}:
            state, action = PersistentEventStoreState.blocked, "complete-event-bus-governance"
            reasons.append("Event-bus governance has not authorized persistent storage")
        elif not broker_allowed:
            state, action = PersistentEventStoreState.configuration_required, "select-approved-broker-adapter"
            reasons.append("Broker type is not approved by policy")
        elif not dependency_ready:
            state, action = PersistentEventStoreState.adapter_unavailable, "install-and-verify-broker-adapter"
            reasons.append("Broker adapter dependency or factory is unavailable")
        elif policy.prohibit_raw_credentials and not credentials_safe:
            state, action = PersistentEventStoreState.blocked, "enforce-isolated-encrypted-broker-credentials"
            reasons.append("Broker credentials or transport encryption violate policy")
        elif not retention_safe or (payload.compaction_enabled and not policy.allow_compaction):
            state, action = PersistentEventStoreState.retention_rejected, "repair-retention-or-compaction-policy"
            reasons.append("Retention or compaction configuration violates policy")
        elif not offset_safe:
            state, action = PersistentEventStoreState.offset_conflict, "repair-consumer-offset-state"
            reasons.append("Consumer offset regressed, exceeded watermark or lag budget")
        elif not ack_safe or not guarantee_safe or not effectively_once_safe:
            state, action = PersistentEventStoreState.configuration_required, "repair-delivery-guarantee-and-ack-mode"
            reasons.append("Delivery guarantee or acknowledgement mode is unsafe")
        elif not persistence_ready or not latency_safe or not replication_safe:
            state, action = PersistentEventStoreState.adapter_unavailable, "verify-persistent-broker-runtime"
            reasons.append("Persistence, latency, replication, stream or consumer-group checks failed")
        else:
            state, action = PersistentEventStoreState.store_ready, "accept-persistent-event-store"
            reasons.append("Broker adapter passed persistence, offset, delivery and security gates")

        dispatchable = state == PersistentEventStoreState.store_ready
        if dispatchable:
            state = PersistentEventStoreState.dispatched
            action = "dispatch-persistent-store-contract-to-v18-63"
            reasons.append("Persistent event-store contract is ready for event-bus integration")

        adapter_score = 100 if dependency_ready and observation.connection_verified else 0
        persistence_score = 100 if persistence_ready and replication_safe else 0
        delivery_score = 100 if ack_safe and guarantee_safe and effectively_once_safe else 0
        offset_score = 100 if offset_safe and offset.acknowledgement_persisted else (70 if offset_safe else 0)
        security_score = 100 if credentials_safe else 0
        confidence = round(
            (adapter_score + persistence_score + delivery_score + offset_score + security_score) / 5
        )

        record = PersistentEventStoreAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            event_bus_assessment_id=payload.event_bus_assessment_id,
            adapter_id=payload.adapter_id,
            broker_type=payload.broker_type,
            stream_name=payload.stream_name,
            consumer_group=payload.consumer_group,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-event-bus" if dispatchable else None,
            consumer_lag=consumer_lag,
            recommended_action=action,
            scores=PersistentEventStoreScores(
                adapter_readiness=adapter_score,
                persistence_integrity=persistence_score,
                delivery_safety=delivery_score,
                offset_integrity=offset_score,
                security_quality=security_score,
                store_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._store_keys.add(store_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                assessment_id=record.id,
                actor_id=payload.actor_id,
                action=action,
            )
        )
        return record

    def list_assessments(self, workspace_id: str) -> list[PersistentEventStoreAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> PersistentEventStoreAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PersistentEventStoreStatusResponse:
        items = self.list_assessments(workspace_id)
        return PersistentEventStoreStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            ready_stores=sum(item.state == PersistentEventStoreState.dispatched for item in items),
            offset_conflicts=sum(item.state == PersistentEventStoreState.offset_conflict for item in items),
            latest_state=items[-1].state if items else None,
        )


executive_persistent_event_store_service = ExecutivePersistentEventStoreService()
