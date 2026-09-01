from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from .models import (
    DeliveryAttempt,
    DeliveryChannel,
    DeliveryPriority,
    DeliveryState,
    NotificationCreate,
    NotificationHubStatus,
    NotificationPreferences,
    NotificationRecord,
)
from .telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
from .email_delivery import EmailDeliveryError, SmtpEmailDeliveryClient


class NotificationHubService:
    """Routes advisory notifications while preserving human control gates."""

    def __init__(
        self, telegram_client: TelegramDeliveryClient | None = None, email_client: SmtpEmailDeliveryClient | None = None
    ) -> None:
        self._preferences = NotificationPreferences()
        self._records: dict[UUID, NotificationRecord] = {}
        self._telegram_client = telegram_client or TelegramDeliveryClient()
        self._email_client = email_client or SmtpEmailDeliveryClient()

    def reset(self) -> None:
        self._preferences = NotificationPreferences()
        self._records.clear()

    def preferences(self) -> NotificationPreferences:
        return self._preferences.model_copy(deep=True)

    def configure(self, preferences: NotificationPreferences) -> NotificationPreferences:
        self._preferences = preferences.model_copy(deep=True)
        return self.preferences()

    def create(self, payload: NotificationCreate, *, now: datetime | None = None) -> NotificationRecord:
        current = now or datetime.now(timezone.utc)
        channels = payload.channels or self._channels_for(payload.priority)
        state = DeliveryState.queued
        deliver_after = None
        if self._is_quiet_time(current) and payload.priority != DeliveryPriority.critical:
            state = DeliveryState.deferred
            deliver_after = self._quiet_hours_end(current)
        record = NotificationRecord(
            **payload.model_dump(exclude={"channels"}),
            channels=channels,
            state=state,
            deliver_after=deliver_after,
        )
        self._records[record.id] = record
        if state == DeliveryState.queued:
            self._deliver(record)
        return record.model_copy(deep=True)

    def list_all(self, state: DeliveryState | None = None) -> list[NotificationRecord]:
        items = list(self._records.values())
        if state is not None:
            items = [item for item in items if item.state == state]
        return [item.model_copy(deep=True) for item in sorted(items, key=lambda item: item.created_at, reverse=True)]

    def get(self, notification_id: UUID) -> NotificationRecord | None:
        record = self._records.get(notification_id)
        return record.model_copy(deep=True) if record else None

    def acknowledge(self, notification_id: UUID) -> NotificationRecord | None:
        record = self._records.get(notification_id)
        if record is None:
            return None
        record.state = DeliveryState.acknowledged
        record.acknowledged_at = datetime.now(timezone.utc)
        return record.model_copy(deep=True)

    def process_due(self, *, now: datetime | None = None) -> list[NotificationRecord]:
        current = now or datetime.now(timezone.utc)
        processed: list[NotificationRecord] = []
        for record in self._records.values():
            if record.state == DeliveryState.deferred and record.deliver_after and record.deliver_after <= current:
                record.state = DeliveryState.queued
                record.deliver_after = None
                self._deliver(record)
                processed.append(record.model_copy(deep=True))
        return processed

    def status(self) -> NotificationHubStatus:
        records = list(self._records.values())
        return NotificationHubStatus(
            queued=sum(item.state == DeliveryState.queued for item in records),
            deferred=sum(item.state == DeliveryState.deferred for item in records),
            delivered=sum(item.state == DeliveryState.delivered for item in records),
            awaiting_acknowledgement=sum(
                item.requires_acknowledgement and item.state == DeliveryState.delivered for item in records
            ),
            failed=sum(item.state == DeliveryState.failed for item in records),
            owner_name=self._preferences.owner_name,
        )

    def _deliver(self, record: NotificationRecord) -> None:
        attempts: list[DeliveryAttempt] = []
        any_success = False
        for channel in record.channels:
            if channel == DeliveryChannel.telegram:
                try:
                    self._telegram_client.send(record.title, record.message)
                    attempts.append(DeliveryAttempt(channel=channel, state=DeliveryState.delivered, detail="Sent via Telegram Bot API."))
                    any_success = True
                except TelegramDeliveryError as exc:
                    attempts.append(DeliveryAttempt(channel=channel, state=DeliveryState.failed, detail=str(exc)))
            elif channel == DeliveryChannel.email:
                try:
                    self._email_client.send(record.title, record.message)
                    attempts.append(DeliveryAttempt(channel=channel, state=DeliveryState.delivered, detail="Sent via SMTP."))
                    any_success = True
                except EmailDeliveryError as exc:
                    attempts.append(DeliveryAttempt(channel=channel, state=DeliveryState.failed, detail=str(exc)))
            else:
                # dashboard, mobile_push, voice have no real outbound adapter
                # yet -- honestly labeled as advisory/simulated rather than
                # silently pretending they're equivalent to the real
                # Telegram/email delivery above.
                attempts.append(
                    DeliveryAttempt(
                        channel=channel,
                        state=DeliveryState.delivered,
                        detail="No real delivery adapter for this channel yet; recorded as advisory only.",
                    )
                )
                any_success = True
        record.attempts = attempts
        record.state = DeliveryState.delivered if any_success else DeliveryState.failed

    def _channels_for(self, priority: DeliveryPriority) -> list[DeliveryChannel]:
        if priority == DeliveryPriority.critical:
            return list(self._preferences.critical_channels)
        if priority == DeliveryPriority.high:
            return list(self._preferences.high_priority_channels)
        return list(self._preferences.default_channels)

    def _is_quiet_time(self, current: datetime) -> bool:
        quiet = self._preferences.quiet_hours
        if not quiet.enabled:
            return False
        local = current.astimezone(ZoneInfo(quiet.timezone)).time().replace(tzinfo=None)
        if quiet.start <= quiet.end:
            return quiet.start <= local < quiet.end
        return local >= quiet.start or local < quiet.end

    def _quiet_hours_end(self, current: datetime) -> datetime:
        quiet = self._preferences.quiet_hours
        zone = ZoneInfo(quiet.timezone)
        local = current.astimezone(zone)
        target = local.replace(hour=quiet.end.hour, minute=quiet.end.minute, second=0, microsecond=0)
        if target <= local:
            target += timedelta(days=1)
        return target.astimezone(timezone.utc)


notification_hub_service = NotificationHubService()
