from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.notification_hub.models import DeliveryState, NotificationRecord
from app.notification_hub.service import notification_hub_service

from .media_pool_service import media_pool_service
from .models import ContentCandidate, ContentStatus
from .platform_strategy import PlatformStrategy, platform_strategy_store
from .posting_schedule import NOTE, PostingWindow, suggested_windows_for_weekday
from .service import instagram_content_service


class InstagramDashboard(BaseModel):
    """One real, aggregated view of the whole Instagram vertical -- what
    needs a decision right now, what's queued behind it, and what state
    the account's rules/pool are in. Every number here is computed live
    from the actual services, not cached or estimated."""

    needs_your_review: int = Field(description="Proposed candidates waiting on your approve/reject decision.")
    moderation_rejected_pending_override: int = Field(
        description="Auto-rejected candidates -- still overridable via /decision if the rejection was wrong."
    )
    approved_ready_to_publish: int
    posted_total: int
    post_failed: int
    media_pool_available: int = Field(description="Photos/videos ingested and not yet used in any post.")
    media_pool_used: int
    curated_drafts_pending: int = Field(description="Grouped by /curate, reserved, waiting on a caption via /finalize.")
    recent_candidates: list[ContentCandidate] = Field(description="Most recent candidates across all statuses.")
    platform_strategy: PlatformStrategy
    todays_posting_windows: list[PostingWindow]
    posting_windows_note: str
    recent_notifications: list[NotificationRecord] = Field(
        description="Recent notification_hub deliveries for this domain -- shows whether you were actually notified, "
        "not just that a candidate exists. A notification here in state 'failed' with no working channel "
        "configured means a real post is waiting and you were never told."
    )
    notifications_delivered_today: int
    notifications_failed_today: int
    unacknowledged_critical_notifications: int = Field(
        description="Notifications requiring acknowledgement (e.g. publish failures) that haven't been seen yet."
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def build_dashboard(recent_limit: int = 10) -> InstagramDashboard:
    all_candidates: list[ContentCandidate] = instagram_content_service.list_all()

    def count(status: ContentStatus) -> int:
        return sum(1 for c in all_candidates if c.status == status)

    pool_items = media_pool_service.list_all()
    today_weekday = datetime.now(timezone.utc).weekday()

    now = datetime.now(timezone.utc)
    instagram_notifications = [n for n in notification_hub_service.list_all() if n.domain == "instagram"]
    today_notifications = [n for n in instagram_notifications if n.created_at.date() == now.date()]

    return InstagramDashboard(
        needs_your_review=count(ContentStatus.proposed),
        moderation_rejected_pending_override=count(ContentStatus.moderation_rejected),
        approved_ready_to_publish=count(ContentStatus.approved),
        posted_total=count(ContentStatus.posted),
        post_failed=count(ContentStatus.post_failed),
        media_pool_available=sum(1 for i in pool_items if i.available),
        media_pool_used=sum(1 for i in pool_items if i.used),
        curated_drafts_pending=len(media_pool_service.list_drafts(pending_only=True)),
        recent_candidates=all_candidates[:recent_limit],
        platform_strategy=platform_strategy_store.current(),
        todays_posting_windows=suggested_windows_for_weekday(today_weekday),
        posting_windows_note=NOTE,
        recent_notifications=instagram_notifications[:recent_limit],
        notifications_delivered_today=sum(1 for n in today_notifications if n.state == DeliveryState.delivered),
        notifications_failed_today=sum(1 for n in today_notifications if n.state == DeliveryState.failed),
        unacknowledged_critical_notifications=sum(
            1 for n in instagram_notifications if n.requires_acknowledgement and n.state == DeliveryState.delivered
        ),
    )
