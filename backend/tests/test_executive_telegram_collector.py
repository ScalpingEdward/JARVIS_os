import pytest

from app.executive_telegram_collector.models import TelegramCollectorAssessmentCreate, TelegramCollectorState
from app.executive_telegram_collector.service import ExecutiveTelegramCollectorService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        collector_id="telethon-main",
        telegram_chat_id="chat-1",
        telegram_message_id="msg-1",
        telegram_sender_id="sender-1",
        session_reference="secret://telegram/session-main",
        session_resolved=True,
        session_file_embedded=False,
        source_allowlisted=True,
        read_only_client=True,
        message_age_seconds=30,
        media_present=True,
        media_reference="media://chat-1/msg-1/image",
        mime_type="image/png",
        size_bytes=500_000,
        width=1920,
        height=1080,
        retrieval_attempts=1,
        retrieval_success=True,
        retryable_failure=False,
        image_sha256="a" * 64,
        caption="XAUUSD M15 ICT setup",
        risk_brain_clear=True,
    )
    data.update(overrides)
    return TelegramCollectorAssessmentCreate(**data)


def test_valid_media_dispatches_to_ingestion():
    result = ExecutiveTelegramCollectorService().create(payload())
    assert result.state == TelegramCollectorState.dispatched
    assert result.dispatchable is True
    assert result.target_module == "executive-telegram-media-ingestion"


def test_missing_isolated_session_is_blocked_before_collection():
    result = ExecutiveTelegramCollectorService().create(payload(session_reference=None, session_resolved=False))
    assert result.state == TelegramCollectorState.session_required
    assert result.dispatchable is False


def test_unknown_source_is_rejected():
    result = ExecutiveTelegramCollectorService().create(payload(source_allowlisted=False))
    assert result.state == TelegramCollectorState.source_rejected


def test_retryable_retrieval_is_bounded_and_queued():
    result = ExecutiveTelegramCollectorService().create(
        payload(retrieval_success=False, retryable_failure=True, retrieval_attempts=1, media_reference=None, image_sha256=None)
    )
    assert result.state == TelegramCollectorState.retrieval_queued


def test_risk_brain_blocks_collection():
    result = ExecutiveTelegramCollectorService().create(payload(risk_brain_clear=False))
    assert result.state == TelegramCollectorState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveTelegramCollectorService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
