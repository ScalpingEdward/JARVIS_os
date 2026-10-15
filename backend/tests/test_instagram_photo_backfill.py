"""Grading photos that were analyzed before photos were graded: fetched back
from Drive through n8n (mocked here), graded for real, recorded."""

from __future__ import annotations

import shutil
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service
from app.instagram_content.photo_backfill import grade_existing_photos

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), (10, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("AURON_DRIVE_FETCH_SECRET", "s")
    monkeypatch.delenv("AURON_COLOR_LUT", raising=False)
    MediaPoolService().reset()
    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(media_ref=f"photo-{i}", media_type="image", theme="t", aesthetic_score=0.7)
        for i in range(3)
    ] + [MediaPoolItemCreate(media_ref="known-bad-1", media_type="image", theme="t", aesthetic_score=0.7)]))


def _client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["id"] == "known-bad-1":
            return httpx.Response(200, content=b"")  # how n8n answers an unknown Drive id
        return httpx.Response(200, content=_jpeg())

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_batch_grades_what_it_can_and_names_what_it_could_not():
    first = grade_existing_photos(limit=2, client=_client())
    assert first["graded"] + len(first["failed"]) == 2

    rest = grade_existing_photos(limit=10, client=_client())
    graded = {i.media_ref: i.processed_file for i in media_pool_service.list_all()}
    assert graded == {"photo-0": "photo-0.jpg", "photo-1": "photo-1.jpg", "photo-2": "photo-2.jpg",
                      "known-bad-1": None}
    assert "no bytes" in {**first["failed"], **rest["failed"]}["known-bad-1"]
    assert rest["remaining"] == 1, "the one that failed stays in the queue for the next batch"
    assert media_pool_service.pending_uploads().count == 3
