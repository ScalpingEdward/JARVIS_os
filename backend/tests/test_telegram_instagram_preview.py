"""The preview upload against a mocked n8n and a mocked Telegram: where the
bytes come from, what is refused, and what Telegram is asked to show."""

from __future__ import annotations

import json
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.instagram_content.models import ContentCandidate, MediaItem
from app.notification_hub.telegram_delivery import TelegramDeliveryConfig
from app.telegram_instagram import preview as preview_module
from app.instagram_content import drive_fetch
from app.instagram_content.drive_fetch import DriveFetchConfig
from app.telegram_instagram.preview import PostPreviewSender, PreviewError


def _jpeg(size=(4032, 3024)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _candidate(*refs: str) -> ContentCandidate:
    return ContentCandidate(
        media_items=[MediaItem(media_ref=r, media_type="image", aesthetic_score=0.7) for r in refs],
        post_format="carousel", format_reasoning="test", caption_draft="x",
    )


def _sender(handler, secret="s3cret") -> PostPreviewSender:
    return PostPreviewSender(
        config=DriveFetchConfig(url="http://n8n/webhook/auron-drive-file", secret=secret),
        telegram=TelegramDeliveryConfig(bot_token="t", chat_id="42"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture(autouse=True)
def _no_processed_files(monkeypatch):
    monkeypatch.setattr(PostPreviewSender, "_processed_file", lambda self, ref: None)


def test_photos_come_from_n8n_with_the_secret_and_go_out_numbered_and_shrunk():
    seen: dict = {"fetch": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "n8n":
            seen["fetch"].append((request.url.params["id"], request.headers.get("x-auron-secret")))
            return httpx.Response(200, content=_jpeg())
        seen["method"] = request.url.path.rsplit("/", 1)[-1]
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "result": []})

    assert _sender(handler).send(_candidate("ref-one-123", "ref-two-456")) == 2

    assert seen["fetch"] == [("ref-one-123", "s3cret"), ("ref-two-456", "s3cret")]
    assert seen["method"] == "sendMediaGroup"
    body = seen["body"].decode("latin-1")
    media = json.loads(body.split('name="media"')[1].split("\r\n\r\n", 1)[1].split("\r\n--", 1)[0])
    assert [m["caption"] for m in media] == ["1", "2"]
    # a 4032 px original goes out at the preview size, not as 4 MB
    assert len(seen["body"]) < 2 * 1024 * 1024


def test_without_the_secret_nothing_is_asked_of_n8n():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not be reached
        raise AssertionError("no request expected")

    with pytest.raises(PreviewError, match="AURON_DRIVE_FETCH_SECRET"):
        _sender(handler, secret=None).send(_candidate("ref-one-123"))


def test_an_empty_answer_from_n8n_is_a_failure_not_an_empty_photo():
    """n8n's Drive node answers an unknown id with an empty 200."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    with pytest.raises(PreviewError, match="no bytes"):
        _sender(handler).send(_candidate("ref-one-123"))


def test_a_file_too_big_for_telegram_is_refused_while_downloading(monkeypatch):
    monkeypatch.setattr(preview_module, "MAX_UPLOAD_BYTES", 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    with pytest.raises(PreviewError, match="larger than"):
        _sender(handler).send(_candidate("ref-one-123"))
