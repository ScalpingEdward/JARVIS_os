"""What curation left lying, shown rather than decided."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service
from app.notification_hub.telegram_delivery import TelegramDeliveryConfig
from app.telegram_instagram.leftovers import leftover_photos, send_leftovers
from app.telegram_instagram.preview import PostPreviewSender
from tests.helpers_multipart import media_json


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (800, 600), (120, 80, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _create(ref, score, day, theme="beach"):
    return MediaPoolItemCreate(
        media_ref=ref, media_type="image", theme=theme, aesthetic_score=score,
        captured_at=datetime(2024, 1, day, 12, 0, tzinfo=timezone.utc),
        captured_at_source="exif", tags=["sand", "sea"],
    )


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(PostPreviewSender, "_processed_file", lambda self, ref: None)
    MediaPoolService().reset()
    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        _create("weak", 0.2, 3), _create("middle", 0.5, 2), _create("good", 0.7, 1),
    ]))
    yield


def _sender(seen: dict) -> PostPreviewSender:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "n8n":
            return httpx.Response(200, content=_jpeg())
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "result": []})

    from app.instagram_content.drive_fetch import DriveFetchConfig

    return PostPreviewSender(
        config=DriveFetchConfig(url="http://n8n/webhook/auron-drive-file", secret="s"),
        telegram=TelegramDeliveryConfig(bot_token="t", chat_id="42"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_leftovers_come_oldest_first_and_weak_ones_can_be_left_out():
    assert [i.media_ref for i in leftover_photos()] == ["good", "middle", "weak"]
    assert [i.media_ref for i in leftover_photos(min_score=0.4)] == ["good", "middle"]


def test_a_favourite_is_not_a_leftover():
    media_pool_service.set_favorite("weak")
    assert "weak" not in [i.media_ref for i in leftover_photos()]


def test_every_caption_names_the_photo_its_score_and_its_day():
    seen: dict = {}
    batch = send_leftovers(min_score=0.4, sender=_sender(seen), client=None)

    assert batch.sent == 2
    assert batch.refs == ["good", "middle"]
    media = media_json(seen["body"])
    assert "0.70" in media[0]["caption"] and "2024-01-01" in media[0]["caption"]
    assert "good" in media[0]["caption"], "the media_ref is how Brano names the one he wants"


def test_a_second_batch_starts_where_the_first_stopped():
    seen: dict = {}
    first = send_leftovers(min_score=0.0, offset=0, limit=2, sender=_sender(seen))
    second = send_leftovers(min_score=0.0, offset=2, limit=2, sender=_sender(seen))

    assert first.refs == ["good", "middle"]
    assert first.remaining == 1
    assert second.refs == ["weak"]
    assert second.remaining == 0


def test_singles_only_keeps_the_photos_that_are_alone_on_their_day():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        _create("pair-a", 0.5, 9), _create("pair-b", 0.5, 9),
    ]))
    refs = [i.media_ref for i in leftover_photos(singles_only=True)]

    assert "pair-a" not in refs and "pair-b" not in refs, "two from one day can still pair up"
    assert refs == ["good", "middle", "weak"]


def test_a_frozen_review_list_keeps_the_numbers_meaning_the_same(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    from app.telegram_instagram.leftovers import ref_for_number, review_list, start_review

    assert start_review(singles_only=False) == ["good", "middle", "weak"]
    media_pool_service.set_favorite("good")  # the pool shifts under it

    assert review_list() == ["good", "middle", "weak"]
    assert ref_for_number(2) == "middle"
    assert ref_for_number(99) is None


def test_the_second_batch_carries_on_the_numbering(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    from app.telegram_instagram.leftovers import start_review

    start_review(singles_only=False)
    seen: dict = {}
    send_leftovers(offset=1, limit=1, sender=_sender(seen), use_review_list=True)

    body = seen["body"].decode("latin-1")
    media = media_json(seen["body"])
    assert media[0]["caption"].startswith("Nr. 2 ")
