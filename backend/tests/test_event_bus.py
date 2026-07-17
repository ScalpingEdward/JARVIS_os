import pytest

from app.event_bus.models import (
    DeliveryMutation, EventPublish, EventState, ReplayRequest, SubscriptionCreate,
    TopicCreate, TopicState,
)
from app.event_bus.service import EventBusService


def active_topic(service: EventBusService, workspace: str = "w1"):
    topic = service.create_topic(TopicCreate(workspace_id=workspace, owner_id="owner", topic_key="trading.signals"))
    return service.set_topic_state(topic.id, workspace, "owner", TopicState.ACTIVE)


def test_publish_filter_delivery_and_metrics():
    service = EventBusService()
    topic = active_topic(service)
    sub = service.create_subscription(SubscriptionCreate(
        workspace_id="w1", owner_id="owner", topic_id=topic.id,
        subscriber_module="strategy_builder", event_types=["SignalReceived"],
        filter_fields={"symbol": "XAUUSD"}, max_retries=1,
    ))
    event = service.publish(EventPublish(
        workspace_id="w1", publisher_id="telegram", source_module="telegram",
        topic_id=topic.id, event_type="SignalReceived", correlation_id="corr-1",
        payload={"symbol": "XAUUSD", "direction": "buy"},
    ))
    assert event.matching_subscription_ids == [sub.id]
    assert service.record_delivery(event.id, "w1", DeliveryMutation(requester_id="owner", success=False, reason="temporary")).state == EventState.FAILED
    assert service.record_delivery(event.id, "w1", DeliveryMutation(requester_id="owner", success=False, reason="again")).state == EventState.DEAD_LETTER
    metrics = service.metrics("w1")
    assert metrics.dead_letter == 1
    assert metrics.retries == 2


def test_replay_is_planning_only_and_workspace_isolated():
    service = EventBusService()
    topic = active_topic(service)
    event = service.publish(EventPublish(
        workspace_id="w1", publisher_id="vision", source_module="vision",
        topic_id=topic.id, event_type="ChartAnalyzed", correlation_id="corr-2",
    ))
    replay = service.plan_replay(ReplayRequest(workspace_id="w1", requester_id="owner", event_ids=[event.id], reason="debug"))
    assert replay.state == "planned"
    assert service.events[event.id].state == EventState.REPLAY_PLANNED
    with pytest.raises(ValueError):
        service.plan_replay(ReplayRequest(workspace_id="w2", requester_id="owner", event_ids=[event.id], reason="wrong workspace"))
    with pytest.raises(ValueError):
        ReplayRequest(workspace_id="w1", requester_id="owner", event_ids=[event.id], reason="unsafe", automatic_replay=True)


def test_safety_duplicate_subscription_and_external_blocking():
    service = EventBusService()
    topic = active_topic(service)
    payload = SubscriptionCreate(workspace_id="w1", owner_id="owner", topic_id=topic.id, subscriber_module="notify")
    service.create_subscription(payload)
    with pytest.raises(ValueError):
        service.create_subscription(payload)
    with pytest.raises(ValueError):
        TopicCreate(workspace_id="w1", owner_id="owner", topic_key="system.events", external_broker=True)
    with pytest.raises(ValueError):
        EventPublish(workspace_id="w1", publisher_id="x", source_module="x", topic_id=topic.id, event_type="x", correlation_id="c", execute_action=True)
