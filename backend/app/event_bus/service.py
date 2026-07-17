from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord, DeliveryMutation, EventBusStatus, EventPublish, EventRecord,
    EventState, MetricsRecord, ReplayRecord, ReplayRequest, SubscriptionCreate,
    SubscriptionRecord, SubscriptionState, TopicCreate, TopicRecord, TopicState,
)


class EventBusService:
    def __init__(self) -> None:
        self.topics: dict[UUID, TopicRecord] = {}
        self.subscriptions: dict[UUID, SubscriptionRecord] = {}
        self.events: dict[UUID, EventRecord] = {}
        self.replays: dict[UUID, ReplayRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    def status(self) -> EventBusStatus:
        return EventBusStatus(
            topics=len(self.topics), subscriptions=len(self.subscriptions), events=len(self.events),
            dead_letter_events=sum(1 for x in self.events.values() if x.state == EventState.DEAD_LETTER),
            replay_plans=len(self.replays),
        )

    def create_topic(self, payload: TopicCreate) -> TopicRecord:
        if any(x.workspace_id == payload.workspace_id and x.topic_key == payload.topic_key and x.state != TopicState.RETIRED for x in self.topics.values()):
            raise ValueError("active topic already exists")
        item = TopicRecord(**payload.model_dump())
        self.topics[item.id] = item
        self._audit(item.workspace_id, "topic.created", "topic", item.id, item.owner_id)
        return item

    def list_topics(self, workspace_id: str) -> list[TopicRecord]:
        return [x for x in self.topics.values() if x.workspace_id == workspace_id]

    def set_topic_state(self, topic_id: UUID, workspace_id: str, requester_id: str, state: TopicState) -> TopicRecord | None:
        item = self.topics.get(topic_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"topic.{state.value}", "topic", item.id, requester_id)
        return item

    def create_subscription(self, payload: SubscriptionCreate) -> SubscriptionRecord:
        topic = self.topics.get(payload.topic_id)
        if not topic or topic.workspace_id != payload.workspace_id or topic.state != TopicState.ACTIVE:
            raise ValueError("active workspace topic not found")
        if any(x.workspace_id == payload.workspace_id and x.topic_id == payload.topic_id and x.subscriber_module == payload.subscriber_module and x.state == SubscriptionState.ACTIVE for x in self.subscriptions.values()):
            raise ValueError("active subscription already exists")
        item = SubscriptionRecord(**payload.model_dump())
        self.subscriptions[item.id] = item
        self._audit(item.workspace_id, "subscription.created", "subscription", item.id, item.owner_id)
        return item

    def list_subscriptions(self, workspace_id: str) -> list[SubscriptionRecord]:
        return [x for x in self.subscriptions.values() if x.workspace_id == workspace_id]

    @staticmethod
    def _matches(subscription: SubscriptionRecord, event: EventPublish) -> bool:
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False
        return all(event.payload.get(key) == value or event.metadata.get(key) == value for key, value in subscription.filter_fields.items())

    def publish(self, payload: EventPublish) -> EventRecord:
        topic = self.topics.get(payload.topic_id)
        if not topic or topic.workspace_id != payload.workspace_id or topic.state != TopicState.ACTIVE:
            raise ValueError("active workspace topic not found")
        if payload.event_type in topic.critical_event_types and not payload.human_approved:
            raise ValueError("critical event requires human approval")
        matching = [x.id for x in self.subscriptions.values() if x.workspace_id == payload.workspace_id and x.topic_id == payload.topic_id and x.state == SubscriptionState.ACTIVE and self._matches(x, payload)]
        data = payload.model_dump(exclude={"human_approved", "execute_action", "publish_external"})
        item = EventRecord(**data, matching_subscription_ids=matching)
        self.events[item.id] = item
        self._audit(item.workspace_id, "event.published", "event", item.id, item.publisher_id, matches=len(matching), correlation_id=item.correlation_id)
        return item

    def list_events(self, workspace_id: str, correlation_id: str | None = None) -> list[EventRecord]:
        return [x for x in self.events.values() if x.workspace_id == workspace_id and (correlation_id is None or x.correlation_id == correlation_id)]

    def record_delivery(self, event_id: UUID, workspace_id: str, payload: DeliveryMutation) -> EventRecord | None:
        item = self.events.get(event_id)
        if not item or item.workspace_id != workspace_id:
            return None
        if payload.success:
            item.state = EventState.ACKNOWLEDGED
        else:
            item.retry_count += 1
            item.failure_reason = payload.reason
            max_retries = max((self.subscriptions[s].max_retries for s in item.matching_subscription_ids if s in self.subscriptions), default=0)
            item.state = EventState.DEAD_LETTER if item.retry_count > max_retries else EventState.FAILED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"event.{item.state.value}", "event", item.id, payload.requester_id, retries=item.retry_count, reason=payload.reason)
        return item

    def plan_replay(self, payload: ReplayRequest) -> ReplayRecord:
        source = [self.events.get(i) for i in payload.event_ids]
        if any(x is None or x.workspace_id != payload.workspace_id for x in source):
            raise ValueError("invalid workspace event selection")
        for item in source:
            item.state = EventState.REPLAY_PLANNED
            item.updated_at = datetime.now(timezone.utc)
        record = ReplayRecord(workspace_id=payload.workspace_id, requester_id=payload.requester_id, source_event_ids=payload.event_ids, reason=payload.reason)
        self.replays[record.id] = record
        self._audit(record.workspace_id, "replay.planned", "replay", record.id, record.requester_id, events=len(record.source_event_ids))
        return record

    def list_dead_letter(self, workspace_id: str) -> list[EventRecord]:
        return [x for x in self.events.values() if x.workspace_id == workspace_id and x.state == EventState.DEAD_LETTER]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        events = [x for x in self.events.values() if x.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            topics=sum(1 for x in self.topics.values() if x.workspace_id == workspace_id),
            subscriptions=sum(1 for x in self.subscriptions.values() if x.workspace_id == workspace_id),
            events=len(events), published=sum(1 for x in events if x.state == EventState.PUBLISHED),
            acknowledged=sum(1 for x in events if x.state == EventState.ACKNOWLEDGED),
            failed=sum(1 for x in events if x.state == EventState.FAILED),
            dead_letter=sum(1 for x in events if x.state == EventState.DEAD_LETTER),
            replay_plans=sum(1 for x in self.replays.values() if x.workspace_id == workspace_id),
            retries=sum(x.retry_count for x in events),
            queue_length=sum(1 for x in events if x.state in {EventState.PUBLISHED, EventState.FAILED}),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [x for x in self.audit if x.workspace_id == workspace_id]


event_bus_service = EventBusService()
