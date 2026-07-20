from uuid import uuid4

import pytest

from app.executive_event_bus.models import (
    EventBusAssessmentCreate,
    EventBusState,
    EventDeliveryObservation,
    EventEnvelope,
)
from app.executive_event_bus.service import ExecutiveEventBusService


def payload(source_key: str = "event-1", **overrides):
    envelope = overrides.pop("envelope", EventEnvelope(
        event_type="telegram.media.ready",
        workspace_id="ws-1",
        producer="executive-telegram-collector",
        target_module="executive-telegram-media-ingestion",
        payload_schema="telegram-media-ready",
        idempotency_key=source_key,
        payload={"media_reference": "vault://media/1"},
    ))
    data = dict(
        workspace_id="ws-1",
        source_key=source_key,
        actor_id="jarvis",
        envelope=envelope,
        observation=EventDeliveryObservation(),
    )
    data.update(overrides)
    return EventBusAssessmentCreate(**data)


def test_dispatches_valid_event():
    record = ExecutiveEventBusService().create(payload())
    assert record.state == EventBusState.dispatched
    assert record.dispatchable is True


def test_acknowledged_event_is_accepted():
    record = ExecutiveEventBusService().create(payload(observation=EventDeliveryObservation(consumer_acknowledged=True)))
    assert record.state == EventBusState.accepted
    assert record.dispatchable is False


def test_schema_failure_is_rejected():
    record = ExecutiveEventBusService().create(payload(observation=EventDeliveryObservation(schema_valid=False)))
    assert record.state == EventBusState.schema_rejected


def test_transient_failure_is_retried():
    record = ExecutiveEventBusService().create(payload(observation=EventDeliveryObservation(timed_out=True, attempts=2)))
    assert record.state == EventBusState.retry_scheduled


def test_permanent_failure_is_dead_lettered():
    record = ExecutiveEventBusService().create(payload(observation=EventDeliveryObservation(consumer_rejected=True)))
    assert record.state == EventBusState.dead_lettered


def test_risk_brain_blocks_dispatch():
    record = ExecutiveEventBusService().create(payload(risk_brain_clear=False))
    assert record.state == EventBusState.blocked


def test_duplicate_idempotency_key_is_detected():
    service = ExecutiveEventBusService()
    service.create(payload("first"))
    second_envelope = EventEnvelope(
        event_id=uuid4(), event_type="telegram.media.ready", workspace_id="ws-1",
        producer="collector", target_module="ingestion", payload_schema="media",
        idempotency_key="first",
    )
    record = service.create(payload("second", envelope=second_envelope))
    assert record.state == EventBusState.duplicate


def test_workspace_isolation():
    service = ExecutiveEventBusService()
    service.create(payload())
    assert len(service.list_assessments("ws-1")) == 1
    assert service.list_assessments("ws-2") == []


def test_workspace_mismatch_raises():
    envelope = EventEnvelope(
        event_type="x", workspace_id="ws-2", producer="p", target_module="t",
        payload_schema="s", idempotency_key="k",
    )
    with pytest.raises(ValueError):
        ExecutiveEventBusService().create(payload(envelope=envelope))
