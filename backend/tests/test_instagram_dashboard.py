from __future__ import annotations

from fastapi.testclient import TestClient

from app.instagram_content.dashboard import build_dashboard
from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.models import ContentCandidateCreate, ContentDecision
from app.instagram_content.service import instagram_content_service
from app.main import app

api_client = TestClient(app)


def _reset_all():
    instagram_content_service.reset()
    media_pool_service.reset()


def _propose(caption="Quiet mornings. #tradingmindset #discipline #patience"):
    return instagram_content_service.propose(
        ContentCandidateCreate(
            media_items=[{"media_ref": f"img-{caption[:8]}", "media_type": "image", "aesthetic_score": 0.9}],
            caption_draft=caption,
        )
    )


def test_dashboard_counts_reflect_real_candidate_state():
    _reset_all()
    proposed = _propose("First one. #tradingmindset #discipline #patience")
    approved = _propose("Second one. #tradingmindset #discipline #patience")
    instagram_content_service.decide(approved.id, ContentDecision(approved=True, reason="Good"))
    rejected = _propose("Follow4follow please!!")  # moderation-rejected

    summary = build_dashboard()

    assert summary.needs_your_review == 1
    assert summary.approved_ready_to_publish == 1
    assert summary.moderation_rejected_pending_override == 1
    assert summary.posted_total == 0


def test_dashboard_reflects_media_pool_state():
    _reset_all()
    media_pool_service.ingest(
        MediaPoolIngestRequest(
            items=[
                MediaPoolItemCreate(media_ref="a", media_type="image", theme="t", aesthetic_score=0.8),
                MediaPoolItemCreate(media_ref="b", media_type="image", theme="t", aesthetic_score=0.8),
                MediaPoolItemCreate(media_ref="c", media_type="image", theme="t", aesthetic_score=0.8),
            ]
        )
    )
    summary = build_dashboard()
    assert summary.media_pool_available == 3
    assert summary.media_pool_used == 0

    media_pool_service.run_curation()  # 3 same-theme images -> one carousel draft, reserves all three
    summary = build_dashboard()
    assert summary.media_pool_available == 0
    assert summary.curated_drafts_pending == 1


def test_dashboard_recent_candidates_respects_the_limit_and_ordering():
    _reset_all()
    first = _propose("Older. #tradingmindset #discipline #patience")
    second = _propose("Newer. #tradingmindset #discipline #patience")

    summary = build_dashboard(recent_limit=1)
    assert len(summary.recent_candidates) == 1
    assert summary.recent_candidates[0].id == second.id  # most recent first


def test_dashboard_includes_current_platform_strategy_and_posting_windows():
    _reset_all()
    summary = build_dashboard()
    assert summary.platform_strategy.max_hashtags == 5
    assert len(summary.todays_posting_windows) >= 1
    assert "analytics" in summary.posting_windows_note.lower() or "insights" in summary.posting_windows_note.lower()


def test_dashboard_reflects_real_notification_activity():
    from app.notification_hub.service import notification_hub_service

    _reset_all()
    notification_hub_service.reset()
    _propose("Notify me. #tradingmindset #discipline #patience")

    summary = build_dashboard()
    assert len(summary.recent_notifications) == 1
    assert summary.recent_notifications[0].domain == "instagram"
    assert summary.notifications_delivered_today + summary.notifications_failed_today == 1


def test_dashboard_notifications_exclude_other_domains():
    from app.notification_hub.models import DeliveryPriority, NotificationCreate
    from app.notification_hub.service import notification_hub_service

    _reset_all()
    notification_hub_service.reset()
    notification_hub_service.create(
        NotificationCreate(title="Unrelated", message="Not Instagram.", priority=DeliveryPriority.normal, domain="trading")
    )
    _propose("Real one. #tradingmindset #discipline #patience")

    summary = build_dashboard()
    assert len(summary.recent_notifications) == 1
    assert summary.recent_notifications[0].domain == "instagram"


def test_dashboard_via_the_api():
    _reset_all()
    _propose()
    response = api_client.get("/v1/instagram/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["needs_your_review"] == 1
    assert "platform_strategy" in body
    assert "todays_posting_windows" in body
