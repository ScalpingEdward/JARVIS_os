"""The videos that predate processing: fetched back, cut, graded, recorded."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service
from app.instagram_content.video_backfill import process_existing_videos, unprocessed_videos

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _clip(path: Path) -> bytes:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )
    return path.read_bytes()


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("AURON_DRIVE_FETCH_SECRET", "s")
    monkeypatch.delenv("AURON_COLOR_LUT", raising=False)
    (tmp_path / "processed").mkdir()
    MediaPoolService().reset()
    media_pool_service.ingest(MediaPoolIngestRequest(items=[
        MediaPoolItemCreate(media_ref="clip-1", media_type="video", theme="t",
                            aesthetic_score=0.6, duration_seconds=10.0),
        MediaPoolItemCreate(media_ref="clip-gone", media_type="video", theme="t",
                            aesthetic_score=0.6, duration_seconds=10.0),
        MediaPoolItemCreate(media_ref="photo-1", media_type="image", theme="t", aesthetic_score=0.6),
    ]))


def _client(tmp_path: Path) -> httpx.Client:
    payload = _clip(tmp_path / "src.mp4")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["id"] == "clip-gone":
            return httpx.Response(200, content=b"")  # how n8n answers an unknown Drive id
        return httpx.Response(200, content=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_only_videos_without_a_processed_file_are_queued():
    assert sorted(i.media_ref for i in unprocessed_videos()) == ["clip-1", "clip-gone"]


def test_a_batch_processes_what_it_can_and_names_what_it_could_not(tmp_path):
    result = process_existing_videos(limit=5, client=_client(tmp_path))

    assert result["processed"] == 1
    assert "no bytes" in result["failed"]["clip-gone"]
    assert result["remaining"] == 1

    done = {i.media_ref: i.processed_file for i in media_pool_service.list_all()}
    assert done["clip-1"] == "clip-1.mp4"
    assert (Path(tmp_path / "processed") / "clip-1.mp4").is_file()
    assert done["clip-gone"] is None
    assert media_pool_service.pending_uploads().count == 1


def test_the_downloaded_original_does_not_stay_behind(tmp_path):
    process_existing_videos(limit=5, client=_client(tmp_path))
    leftovers = list((tmp_path / "processed").glob("*.src.mp4"))
    assert leftovers == [], "a few hundred MB per clip would fill the disk quietly"


def test_an_offset_works_past_a_clip_that_keeps_failing(tmp_path):
    """One stubborn clip must not mean the whole backlog is retried: that is
    what turned a re-render into two hours of the same three files."""
    assert process_existing_videos(limit=1, offset=0, client=_client(tmp_path))["processed"] == 1

    stuck = process_existing_videos(limit=1, offset=0, client=_client(tmp_path))
    assert list(stuck["failed"]) == ["clip-gone"], "the queue's head is the one that fails"

    skipped = process_existing_videos(limit=5, offset=1, client=_client(tmp_path))
    assert skipped == {"processed": 0, "failed": {}, "remaining": 1},         "past it there is nothing left, and it was not tried again"
