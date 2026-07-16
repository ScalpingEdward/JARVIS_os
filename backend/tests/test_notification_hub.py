from datetime import datetime, timezone

from app.notification_hub.models import (
    DeliveryChannel,
    DeliveryPriority,
    DeliveryState,
    NotificationCreate,
    NotificationPreferences,
    QuietHours,
)
from app.notification_hub.service import notification_hub_service


def setup_function() -> None:
    notification_hub_service.reset()


def test_critical_notification_uses_escalation_channels() -> None:
    record = notification_hub_service.create(
        NotificationCreate(
            title="Critical risk",
            message="Immediate attention, MASTER Brano.",
            priority=DeliveryPriority.critical,
            requires_acknowledgement=True,
        ),
        now=datetime(2026, 7, 16, 21, 0, tzinfo=timezone.utc),
    )
    assert record.state == DeliveryState.delivered
    assert DeliveryChannel.telegram in record.channels
    assert DeliveryChannel.voice in record.channels
    assert record.requires_acknowledgement is True
    assert notification_hub_service.status().awaiting_acknowledgement == 1


def test_quiet_hours_defer_noncritical_notification() -> None:
    notification_hub_service.configure(
        NotificationPreferences(
            quiet_hours=QuietHours(enabled=True, timezone="Europe/Berlin")
        )
    )
    record = notification_hub_service.create(
        NotificationCreate(
            title="Daily summary",
            message="A non-critical update is ready.",
            priority=DeliveryPriority.normal,
        ),
        now=datetime(2026, 7, 16, 22, 30, tzinfo=timezone.utc),
    )
    assert record.state == DeliveryState.deferred
    assert record.deliver_after is not None
    assert not record.attempts


def test_acknowledgement_is_explicit_and_human_controlled() -> None:
    record = notification_hub_service.create(
        NotificationCreate(
            title="Approval required",
            message="Review the proposed action.",
            priority=DeliveryPriority.high,
            requires_acknowledgement=True,
        ),
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )
    acknowledged = notification_hub_service.acknowledge(record.id)
    assert acknowledged is not None
    assert acknowledged.state == DeliveryState.acknowledged
    assert acknowledged.acknowledged_at is not None
    status = notification_hub_service.status()
    assert status.automatic_execution is False
    assert status.automatic_order_execution is False
