"""Catching a handover that was cut short, by a fact rather than a guess.

n8n writes the downloaded video into the handoff directory and nothing
renames it into place afterwards -- the ReadWriteFile node cannot -- so an
interrupted write leaves a partial file sitting there under its final name.

Detecting that from the file's own contents does not work. An MP4 written
with +faststart, which is what phones produce, carries its moov atom at the
front: it survives truncation and ffprobe reads the full original duration
off a half file with complete confidence. Measured against real truncations
of a 20s +faststart file, frame extraction only starts failing from roughly
5% missing -- at 97% and above the file passed with a 20.000s duration that
was simply wrong.

So the check compares the bytes on disk against the size Google Drive itself
reports, before ffprobe is ever invoked. Two numbers, no heuristics, and it
does not care where the moov atom sits or how narrowly the write was cut.
"""

import shutil
import subprocess

import pytest

from app.instagram_content.analyze_and_ingest import _size_mismatch, analyze_and_ingest
from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import MediaType
from app.instagram_content.vision_analysis import VisionAnalysisResult

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed here (they ship in the api image)",
)


class _StubAnalyzer:
    def __init__(self):
        self.called = False

    def analyze(self, **kwargs):
        self.called = True
        return VisionAnalysisResult(
            theme="testsrc-pattern", tags=["synthetic"], aesthetic_score=0.5,
            reasoning="stub", cover_timestamp_seconds=kwargs["frames"][0].timestamp_seconds,
        )


@pytest.fixture
def ingest_dir(tmp_path, monkeypatch):
    root = tmp_path / "ingest"
    root.mkdir()
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(root))
    return root


def _faststart_video(path, seconds: int = 20):
    """+faststart on purpose: the case where truncation is invisible to
    ffprobe, and the one phones actually write."""
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"testsrc=size=640x360:rate=25:duration={seconds}",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
        check=True, capture_output=True, timeout=120,
    )
    return path


# -- the comparison itself --------------------------------------------------


def test_a_matching_size_passes(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x" * 5000)
    assert _size_mismatch(path, 5000) is None


def test_no_expected_size_is_not_a_mismatch(tmp_path):
    """Images and any caller that does not supply one keep working."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x" * 10)
    assert _size_mismatch(path, None) is None


def test_a_short_file_is_refused_and_the_message_names_both_numbers(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x" * 4997)

    message = _size_mismatch(path, 5000)

    assert message is not None
    assert "4997" in message and "5000" in message
    assert "-3" in message, "the shortfall itself is stated"


def test_even_three_bytes_short_is_refused(tmp_path):
    """The gap this closes is narrow truncation, so the check may not have a
    tolerance -- a byte comparison either matches or it does not."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x" * 999_997)
    assert _size_mismatch(path, 1_000_000) is not None


def test_a_longer_file_is_refused_too(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x" * 5001)
    assert _size_mismatch(path, 5000) is not None


def test_a_vanished_file_is_reported_not_crashed(tmp_path):
    assert "cannot stat" in _size_mismatch(tmp_path / "gone.mp4", 5000)


# -- through the ingest path ------------------------------------------------


@ffmpeg_required
def test_a_truncation_ffprobe_cannot_see_is_still_refused(ingest_dir):
    """The decisive case. This file is short by 2% -- frame extraction alone
    lets it through and ffprobe reports the full 20s, so without the size
    check the pool would store a duration that is wrong."""
    source = _faststart_video(ingest_dir / "source.mp4")
    full_size = source.stat().st_size
    clip = ingest_dir / "clip.mp4"
    clip.write_bytes(source.read_bytes()[: int(full_size * 0.98)])
    source.unlink()

    analyzer = _StubAnalyzer()
    service = MediaPoolService()
    service.reset()

    response = analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(
            media_ref="drive-truncated", media_type=MediaType.video,
            video_path="clip.mp4", expected_size_bytes=full_size,
        )],
        analyzer=analyzer,
        pool_service=service,
    )

    assert response.failed == 1
    assert response.analyzed_and_ingested == 0
    assert "handover was incomplete" in response.results[0].error
    assert str(full_size) in response.results[0].error
    assert analyzer.called is False, "refused before any analysis was paid for"
    assert service.list_all() == [], "nothing with a wrong duration reached the pool"


@ffmpeg_required
def test_the_check_runs_before_ffprobe_not_after(ingest_dir):
    """Cheap and first: a file that is not a video at all never reaches
    ffprobe when its size already disagrees."""
    clip = ingest_dir / "clip.mp4"
    clip.write_bytes(b"not a video at all")

    response = analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(
            media_ref="drive-x", media_type=MediaType.video,
            video_path="clip.mp4", expected_size_bytes=999_999,
        )],
        analyzer=_StubAnalyzer(),
        pool_service=MediaPoolService(),
    )

    error = response.results[0].error
    assert "handover was incomplete" in error
    assert "ffprobe" not in error, "it never got that far"


@ffmpeg_required
def test_a_complete_file_passes_the_check_and_is_analyzed(ingest_dir):
    clip = _faststart_video(ingest_dir / "clip.mp4", seconds=6)
    analyzer = _StubAnalyzer()
    service = MediaPoolService()
    service.reset()

    response = analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(
            media_ref="drive-ok", media_type=MediaType.video,
            video_path="clip.mp4", expected_size_bytes=clip.stat().st_size,
        )],
        analyzer=analyzer,
        pool_service=service,
    )

    assert response.failed == 0
    assert analyzer.called is True
    stored = service.list_all()[0]
    assert stored.duration_seconds == pytest.approx(6.0, abs=0.2)


@ffmpeg_required
def test_one_bad_handover_does_not_take_the_batch_with_it(ingest_dir):
    good = _faststart_video(ingest_dir / "good.mp4", seconds=6)
    bad = ingest_dir / "bad.mp4"
    bad.write_bytes(good.read_bytes()[:500])

    response = analyze_and_ingest(
        items=[
            MediaAnalyzeAndIngestItem(
                media_ref="bad", media_type=MediaType.video,
                video_path="bad.mp4", expected_size_bytes=good.stat().st_size,
            ),
            MediaAnalyzeAndIngestItem(
                media_ref="good", media_type=MediaType.video,
                video_path="good.mp4", expected_size_bytes=good.stat().st_size,
            ),
        ],
        analyzer=_StubAnalyzer(),
        pool_service=MediaPoolService(),
    )

    by_ref = {r.media_ref: r for r in response.results}
    assert by_ref["bad"].success is False
    assert by_ref["good"].success is True
