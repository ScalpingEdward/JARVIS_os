from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.notification_hub.models import DeliveryChannel, DeliveryPriority, DeliveryState, NotificationCreate
from app.notification_hub.service import NotificationHubService
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig, TelegramDeliveryError


# -- TelegramDeliveryClient: real, bounded API call --------------------------


def test_send_fails_closed_without_bot_token_or_chat_id():
    client = TelegramDeliveryClient(config=TelegramDeliveryConfig(bot_token=None, chat_id=None))
    with pytest.raises(TelegramDeliveryError, match="TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"):
        client.send("Title", "Message")


def test_send_posts_to_the_real_telegram_api():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})

    client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id="999"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.send("New post ready", "A carousel is waiting for your approval.")

    assert "bot123:ABC/sendMessage" in captured["url"]
    assert captured["body"]["chat_id"] == "999"
    assert "New post ready" in captured["body"]["text"]
    assert "A carousel is waiting" in captured["body"]["text"]


def test_send_raises_on_api_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="bad", chat_id="999"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TelegramDeliveryError, match="401"):
        client.send("Title", "Message")


def test_send_raises_when_telegram_reports_ok_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    client = TelegramDeliveryClient(
        config=TelegramDeliveryConfig(bot_token="123:ABC", chat_id="wrong"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TelegramDeliveryError, match="reported failure"):
        client.send("Title", "Message")


# -- NotificationHubService: real Telegram delivery wired into _deliver -----


def test_delivery_uses_the_real_telegram_client_for_the_telegram_channel():
    sent: list[tuple[str, str]] = []

    class FakeTelegramClient:
        def send(self, title: str, message: str) -> None:
            sent.append((title, message))

    service = NotificationHubService(telegram_client=FakeTelegramClient())
    record = service.create(
        NotificationCreate(
            title="Post ready",
            message="A hero post is waiting for review.",
            priority=DeliveryPriority.high,
        ),
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert record.state == DeliveryState.delivered
    assert sent == [("Post ready", "A hero post is waiting for review.")]
    telegram_attempt = next(a for a in record.attempts if a.channel == DeliveryChannel.telegram)
    assert telegram_attempt.state == DeliveryState.delivered


def test_telegram_failure_is_recorded_but_other_channels_still_deliver():
    class FailingTelegramClient:
        def send(self, title: str, message: str) -> None:
            raise TelegramDeliveryError("bot token invalid")

    service = NotificationHubService(telegram_client=FailingTelegramClient())
    record = service.create(
        NotificationCreate(
            title="Post ready",
            message="Review needed.",
            priority=DeliveryPriority.high,  # dashboard + telegram by default
        ),
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )

    telegram_attempt = next(a for a in record.attempts if a.channel == DeliveryChannel.telegram)
    assert telegram_attempt.state == DeliveryState.failed
    assert "bot token invalid" in telegram_attempt.detail
    # dashboard channel has no real adapter yet but still counts as delivered,
    # so the overall record isn't blocked by telegram alone failing
    assert record.state == DeliveryState.delivered


def test_record_fails_when_every_configured_channel_fails():
    class FailingTelegramClient:
        def send(self, title: str, message: str) -> None:
            raise TelegramDeliveryError("bot token invalid")

    service = NotificationHubService(telegram_client=FailingTelegramClient())
    record = service.create(
        NotificationCreate(
            title="Post ready",
            message="Review needed.",
            priority=DeliveryPriority.normal,
            channels=[DeliveryChannel.telegram],  # only channel, and it fails
        ),
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert record.state == DeliveryState.failed


def test_escalate_overdue_redelivers_an_unacknowledged_critical_notification():
    sent: list[str] = []

    class TrackingTelegramClient:
        def send(self, title: str, message: str) -> None:
            sent.append(title)

    service = NotificationHubService(telegram_client=TrackingTelegramClient())
    created_at = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    record = service.create(
        NotificationCreate(
            title="Publish failed",
            message="Needs attention.",
            priority=DeliveryPriority.high,
            requires_acknowledgement=True,
        ),
        now=created_at,
    )
    assert len(sent) == 1  # initial delivery

    # not yet past the default 10-minute escalation window
    escalated = service.escalate_overdue(now=created_at + timedelta(minutes=5))
    assert escalated == []
    assert len(sent) == 1

    escalated = service.escalate_overdue(now=created_at + timedelta(minutes=11))
    assert len(escalated) == 1
    assert escalated[0].id == record.id
    assert len(sent) == 2  # actually re-delivered, not just flagged


def test_escalate_overdue_skips_acknowledged_notifications():
    service = NotificationHubService(telegram_client=TelegramDeliveryClient(config=TelegramDeliveryConfig(bot_token=None, chat_id=None)))
    created_at = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    record = service.create(
        NotificationCreate(
            title="Publish failed",
            message="Needs attention.",
            priority=DeliveryPriority.high,
            requires_acknowledgement=True,
            channels=[DeliveryChannel.dashboard],  # avoid the real telegram fail-closed path here
        ),
        now=created_at,
    )
    service.acknowledge(record.id)

    escalated = service.escalate_overdue(now=created_at + timedelta(minutes=30))
    assert escalated == []


def test_delivery_uses_the_real_email_client_for_the_email_channel():
    from app.notification_hub.email_delivery import SmtpEmailDeliveryClient

    sent: list[tuple[str, str]] = []

    class FakeEmailClient:
        def send(self, subject: str, body: str) -> None:
            sent.append((subject, body))

    service = NotificationHubService(email_client=FakeEmailClient())
    record = service.create(
        NotificationCreate(
            title="Post ready",
            message="A hero post is waiting for review.",
            priority=DeliveryPriority.normal,
            channels=[DeliveryChannel.email],
        ),
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert record.state == DeliveryState.delivered
    assert sent == [("Post ready", "A hero post is waiting for review.")]
    email_attempt = next(a for a in record.attempts if a.channel == DeliveryChannel.email)
    assert email_attempt.state == DeliveryState.delivered
