from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    DeliveryState,
    NotificationCreate,
    NotificationHubStatus,
    NotificationList,
    NotificationPreferences,
    NotificationRecord,
)
from .service import notification_hub_service


router = APIRouter(prefix="/v1/notification-hub", tags=["notification-hub"])


@router.get("/status", response_model=NotificationHubStatus)
def notification_status() -> NotificationHubStatus:
    return notification_hub_service.status()


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences() -> NotificationPreferences:
    return notification_hub_service.preferences()


@router.put("/preferences", response_model=NotificationPreferences)
def configure_preferences(payload: NotificationPreferences) -> NotificationPreferences:
    return notification_hub_service.configure(payload)


@router.post("/notifications", response_model=NotificationRecord, status_code=status.HTTP_201_CREATED)
def create_notification(payload: NotificationCreate) -> NotificationRecord:
    return notification_hub_service.create(payload)


@router.get("/notifications", response_model=NotificationList)
def list_notifications(state_filter: DeliveryState | None = Query(default=None, alias="state")) -> NotificationList:
    items = notification_hub_service.list_all(state=state_filter)
    return NotificationList(items=items, count=len(items))


@router.get("/notifications/{notification_id}", response_model=NotificationRecord)
def get_notification(notification_id: UUID) -> NotificationRecord:
    record = notification_hub_service.get(notification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return record


@router.post("/notifications/{notification_id}/acknowledge", response_model=NotificationRecord)
def acknowledge_notification(notification_id: UUID) -> NotificationRecord:
    record = notification_hub_service.acknowledge(notification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return record


@router.post("/process-due", response_model=NotificationList)
def process_due_notifications() -> NotificationList:
    items = notification_hub_service.process_due()
    return NotificationList(items=items, count=len(items))


@router.post("/escalate-overdue", response_model=NotificationList)
def escalate_overdue_notifications() -> NotificationList:
    """Re-delivers notifications that required acknowledgement, were sent,
    and still haven't been acknowledged past the configured
    escalation_minutes window. Call this on a schedule alongside
    /process-due."""
    items = notification_hub_service.escalate_overdue()
    return NotificationList(items=items, count=len(items))
