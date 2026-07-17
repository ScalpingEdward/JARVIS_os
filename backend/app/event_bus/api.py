from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    DeliveryMutation, EventBusStatus, EventPublish, EventRecord, MetricsRecord,
    ReplayRecord, ReplayRequest, SubscriptionCreate, SubscriptionRecord,
    TopicCreate, TopicRecord, TopicState,
)
from .service import event_bus_service as service

router = APIRouter(prefix="/v1/event-bus", tags=["event-bus"])


@router.get("/status", response_model=EventBusStatus)
def get_status() -> EventBusStatus:
    return service.status()


@router.post("/topics", response_model=TopicRecord, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate) -> TopicRecord:
    try:
        return service.create_topic(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/topics", response_model=list[TopicRecord])
def list_topics(workspace_id: str = Query(min_length=1, max_length=120)) -> list[TopicRecord]:
    return service.list_topics(workspace_id)


def _set_topic(topic_id: UUID, workspace_id: str, requester_id: str, state: TopicState) -> TopicRecord:
    item = service.set_topic_state(topic_id, workspace_id, requester_id, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned topic not found")
    return item


@router.post("/topics/{topic_id}/activate", response_model=TopicRecord)
def activate_topic(topic_id: UUID, requester_id: str, workspace_id: str = Query(min_length=1, max_length=120)) -> TopicRecord:
    return _set_topic(topic_id, workspace_id, requester_id, TopicState.ACTIVE)


@router.post("/topics/{topic_id}/suspend", response_model=TopicRecord)
def suspend_topic(topic_id: UUID, requester_id: str, workspace_id: str = Query(min_length=1, max_length=120)) -> TopicRecord:
    return _set_topic(topic_id, workspace_id, requester_id, TopicState.SUSPENDED)


@router.post("/topics/{topic_id}/retire", response_model=TopicRecord)
def retire_topic(topic_id: UUID, requester_id: str, workspace_id: str = Query(min_length=1, max_length=120)) -> TopicRecord:
    return _set_topic(topic_id, workspace_id, requester_id, TopicState.RETIRED)


@router.post("/subscriptions", response_model=SubscriptionRecord, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate) -> SubscriptionRecord:
    try:
        return service.create_subscription(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/subscriptions", response_model=list[SubscriptionRecord])
def list_subscriptions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SubscriptionRecord]:
    return service.list_subscriptions(workspace_id)


@router.post("/events", response_model=EventRecord, status_code=status.HTTP_201_CREATED)
def publish_event(payload: EventPublish) -> EventRecord:
    try:
        return service.publish(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events", response_model=list[EventRecord])
def list_events(workspace_id: str = Query(min_length=1, max_length=120), correlation_id: str | None = None) -> list[EventRecord]:
    return service.list_events(workspace_id, correlation_id)


@router.get("/history", response_model=list[EventRecord])
def event_history(workspace_id: str = Query(min_length=1, max_length=120), correlation_id: str | None = None) -> list[EventRecord]:
    return service.list_events(workspace_id, correlation_id)


@router.post("/events/{event_id}/delivery", response_model=EventRecord)
def record_delivery(event_id: UUID, payload: DeliveryMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> EventRecord:
    item = service.record_delivery(event_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Workspace event not found")
    return item


@router.post("/replay", response_model=ReplayRecord, status_code=status.HTTP_201_CREATED)
def plan_replay(payload: ReplayRequest) -> ReplayRecord:
    try:
        return service.plan_replay(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/dead-letter", response_model=list[EventRecord])
def list_dead_letter(workspace_id: str = Query(min_length=1, max_length=120)) -> list[EventRecord]:
    return service.list_dead_letter(workspace_id)


@router.get("/metrics", response_model=MetricsRecord)
def get_metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
