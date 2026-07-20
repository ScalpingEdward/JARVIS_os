import pytest

from app.executive_telegram_media_ingestion.models import IngestionState, TelegramMediaIngestionCreate
from app.executive_telegram_media_ingestion.service import ExecutiveTelegramMediaIngestionService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="chat-1:message-1",
        actor_id="telegram-collector",
        telegram_chat_id="chat-1",
        telegram_message_id="message-1",
        media_reference="telegram://chat-1/message-1/image",
        image_sha256="a" * 64,
        mime_type="image/png",
        size_bytes=500_000,
        width=1920,
        height=1080,
        chat_allowlisted=True,
        malware_scan_clear=True,
        vision_provider_available=True,
    )
    data.update(overrides)
    return TelegramMediaIngestionCreate(**data)


def test_dispatches_allowlisted_readable_chart():
    item = ExecutiveTelegramMediaIngestionService().create(payload())
    assert item.state == IngestionState.dispatched
    assert item.dispatchable is True
    assert item.target_module == "executive-telegram-chart-vision-signal-intelligence"


def test_quarantines_unknown_chat():
    item = ExecutiveTelegramMediaIngestionService().create(payload(chat_allowlisted=False))
    assert item.state == IngestionState.quarantined
    assert item.dispatchable is False


def test_rejects_unsupported_media():
    item = ExecutiveTelegramMediaIngestionService().create(payload(mime_type="application/pdf"))
    assert item.state == IngestionState.rejected


def test_holds_when_vision_provider_is_unavailable():
    item = ExecutiveTelegramMediaIngestionService().create(payload(vision_provider_available=False))
    assert item.state == IngestionState.vision_ready


def test_duplicate_source_and_image_are_blocked():
    service = ExecutiveTelegramMediaIngestionService()
    service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload(source_key="chat-1:message-2"))


def test_workspace_isolation():
    service = ExecutiveTelegramMediaIngestionService()
    item = service.create(payload())
    assert service.get(item.id, "ws-2") is None
    assert service.list_ingestions("ws-2") == []
