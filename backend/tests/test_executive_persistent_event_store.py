from uuid import uuid4

import pytest

from app.executive_persistent_event_store.models import (
    AckMode,
    BrokerAdapterObservation,
    BrokerType,
    ConsumerOffsetObservation,
    DeliveryGuarantee,
    PersistentEventStoreAssessmentCreate,
    PersistentEventStoreState,
)
from app.executive_persistent_event_store.service import ExecutivePersistentEventStoreService


def payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        source_key=str(uuid4()),
        actor_id="tester",
        event_bus_assessment_id=str(uuid4()),
        event_bus_state="dispatched",
        adapter_id="broker-1",
        broker_type=BrokerType.redis_streams,
        stream_name="phoenix-events",
        consumer_group="vision-workers",
        delivery_guarantee=DeliveryGuarantee.at_least_once,
        ack_mode=AckMode.manual,
        retention_hours=168,
        observation=BrokerAdapterObservation(
            connection_verified=True,
            stream_or_topic_exists=True,
            persistence_verified=True,
            consumer_group_verified=True,
            offset_store_verified=True,
            idempotent_producer_verified=True,
            encryption_in_transit_verified=True,
            authentication_reference_resolved=True,
            latency_ms=30,
        ),
        offset=ConsumerOffsetObservation(
            committed_offset=9,
            observed_offset=10,
            high_watermark=10,
            acknowledgement_persisted=True,
        ),
    )
    data.update(overrides)
    return PersistentEventStoreAssessmentCreate(**data)


def test_ready_store_dispatches():
    item = ExecutivePersistentEventStoreService().create(payload())
    assert item.state == PersistentEventStoreState.dispatched
    assert item.dispatchable is True
    assert item.target_module == "executive-event-bus"


def test_missing_adapter_dependency_is_unavailable():
    observation = payload().observation.model_copy(update={"dependency_installed": False})
    item = ExecutivePersistentEventStoreService().create(payload(observation=observation))
    assert item.state == PersistentEventStoreState.adapter_unavailable


def test_raw_credentials_are_blocked():
    observation = payload().observation.model_copy(update={"raw_credentials_present": True})
    item = ExecutivePersistentEventStoreService().create(payload(observation=observation))
    assert item.state == PersistentEventStoreState.blocked


def test_offset_regression_is_detected():
    offset = ConsumerOffsetObservation(
        committed_offset=20,
        observed_offset=10,
        high_watermark=30,
        offset_regression_detected=True,
    )
    item = ExecutivePersistentEventStoreService().create(payload(offset=offset))
    assert item.state == PersistentEventStoreState.offset_conflict


def test_effectively_once_requires_transactional_safety():
    item = ExecutivePersistentEventStoreService().create(
        payload(delivery_guarantee=DeliveryGuarantee.effectively_once, ack_mode=AckMode.manual)
    )
    assert item.state == PersistentEventStoreState.configuration_required


def test_retention_policy_rejects_invalid_window():
    item = ExecutivePersistentEventStoreService().create(payload(retention_hours=10))
    assert item.state == PersistentEventStoreState.retention_rejected


def test_risk_brain_blocks_store():
    item = ExecutivePersistentEventStoreService().create(payload(risk_brain_clear=False))
    assert item.state == PersistentEventStoreState.blocked


def test_duplicate_store_is_rejected():
    service = ExecutivePersistentEventStoreService()
    first = payload(source_key="one")
    service.create(first)
    with pytest.raises(ValueError):
        service.create(payload(source_key="two"))


def test_workspace_isolation():
    service = ExecutivePersistentEventStoreService()
    item = service.create(payload())
    assert service.get(item.id, "ws-b") is None
    assert service.list_assessments("ws-b") == []
