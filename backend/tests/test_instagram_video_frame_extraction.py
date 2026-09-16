"""Sampling still frames out of a video so the vision step has something to
look at.

Videos carry no EXIF and Drive hands out no thumbnail for them, which is why
all 30 videos in the live pool were ingested as placeholders. ffprobe reads
the real duration, ffmpeg samples frames across it, and the same analyzer
that handles photos looks at one of them.

The ffmpeg-backed tests build a real 6-second video with ffmpeg itself and
skip where it is unavailable (it ships in the api image, not necessarily on
a dev machine). The sampling plan and the mismatch warning are pure
arithmetic and always run.
"""

import logging
import shutil
import subprocess

import pytest

from app.instagram_content.media_pool_models import FrameSample
from app.instagram_content.video_frame_extraction import (
    MAX_FRAMES,
    MIN_FRAMES,
    VideoFrameExtractionError,
    extract_frames,
    frame_timestamps,
    probe_duration_seconds,
    representative_frame,
    sample_video,
    warn_on_duration_mismatch,
)

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed here (they ship in the api image)",
)


@pytest.fixture
def real_video(tmp_path):
    """A genuine 6-second MP4, not a fixture file full of zeros."""
    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=6",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True, capture_output=True, timeout=60,
    )
    return path


# -- the sampling plan ------------------------------------------------------


def test_spacing_stays_roughly_constant_across_very_different_lengths():
    """The reason this is not a fixed frame count: constant spacing keeps the
    temporal resolution the same whether the clip is 9s or 46s."""
    for duration in (9.3, 15.31, 28.67, 45.95):
        stamps = frame_timestamps(duration)
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        assert all(2.2 <= gap <= 3.9 for gap in gaps), (duration, gaps)


def test_the_real_pool_durations_produce_the_expected_frame_counts():
    assert len(frame_timestamps(1.13)) == MIN_FRAMES
    assert len(frame_timestamps(9.30)) == 4
    assert len(frame_timestamps(15.31)) == 6
    assert len(frame_timestamps(28.67)) == 11
    assert len(frame_timestamps(45.95)) == 18


def test_a_very_short_clip_still_gets_the_minimum_the_trim_analyzer_needs():
    stamps = frame_timestamps(1.13)
    assert len(stamps) == 3
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == 3, "three distinct points, not the same instant three times"


def test_a_very_long_video_is_capped():
    assert len(frame_timestamps(3600)) == MAX_FRAMES


def test_sampling_avoids_the_first_and_last_frames():
    """The opening frame is regularly black or blurred -- the worst possible
    cover candidate and the least informative sample."""
    duration = 20.0
    stamps = frame_timestamps(duration)
    assert stamps[0] == pytest.approx(1.0)
    assert stamps[-1] == pytest.approx(19.0)
    assert stamps[0] > 0
    assert stamps[-1] < duration


def test_timestamps_are_evenly_spaced_and_ordered():
    stamps = frame_timestamps(30.0)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    # timestamps are rounded to milliseconds, so gaps agree to within one
    assert max(gaps) - min(gaps) <= 0.002
    assert stamps == sorted(stamps)


def test_a_zero_length_video_is_refused():
    with pytest.raises(VideoFrameExtractionError):
        frame_timestamps(0)


# -- ffprobe's duration is the one that counts ------------------------------


def test_a_matching_duration_logs_nothing(caplog):
    with caplog.at_level(logging.WARNING):
        assert warn_on_duration_mismatch(_fake_path(), 9.305, 9.305) is False
    assert caplog.records == []


def test_small_container_rounding_is_tolerated(caplog):
    with caplog.at_level(logging.WARNING):
        assert warn_on_duration_mismatch(_fake_path(), 9.305, 9.30) is False
    assert caplog.records == []


def test_a_real_disagreement_is_logged_with_both_values(caplog):
    with caplog.at_level(logging.WARNING):
        assert warn_on_duration_mismatch(_fake_path(), 45.95, 30.0) is True
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "45.950" in message and "30.000" in message and "using ffprobe" in message


def test_no_claimed_duration_is_not_a_mismatch(caplog):
    with caplog.at_level(logging.WARNING):
        assert warn_on_duration_mismatch(_fake_path(), 9.305, None) is False
    assert caplog.records == []


def _fake_path():
    from pathlib import Path

    return Path("clip.mp4")


# -- against a real file ----------------------------------------------------


@ffmpeg_required
def test_probe_reads_the_real_duration(real_video):
    assert probe_duration_seconds(real_video) == pytest.approx(6.0, abs=0.2)


@ffmpeg_required
def test_extract_frames_returns_one_real_jpeg_per_timestamp(real_video):
    stamps = [1.0, 3.0, 5.0]
    frames = extract_frames(real_video, stamps)

    assert [f.timestamp_seconds for f in frames] == stamps
    for frame in frames:
        assert frame.image_media_type == "image/jpeg"
        import base64

        raw = base64.b64decode(frame.image_base64)
        assert raw.startswith(b"\xff\xd8\xff"), "real JPEG magic bytes"
        assert len(raw) > 1000


@ffmpeg_required
def test_sample_video_uses_ffprobes_duration_not_the_callers(real_video, caplog):
    """The decisive behaviour: a caller claiming 30s for a 6s file must not
    steer the sampling -- otherwise frames get requested past the end."""
    with caplog.at_level(logging.WARNING):
        duration, frames = sample_video(real_video, claimed_duration_seconds=30.0)

    assert duration == pytest.approx(6.0, abs=0.2)
    assert len(frames) == 3, "derived from 6s, not from the claimed 30s"
    assert all(f.timestamp_seconds < duration for f in frames)
    assert any("duration mismatch" in r.getMessage() for r in caplog.records)


@ffmpeg_required
def test_a_file_that_is_not_a_video_fails_with_a_reason(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"this is not a video")

    with pytest.raises(VideoFrameExtractionError):
        probe_duration_seconds(broken)


@ffmpeg_required
def test_an_unreadable_frame_fails_the_extraction_rather_than_shortening_it(real_video):
    """The timestamps are the contract the analysis rests on -- silently
    returning fewer, differently spaced frames would corrupt it."""
    with pytest.raises(VideoFrameExtractionError, match="could not read a frame"):
        extract_frames(real_video, [999.0])


def test_missing_ffmpeg_is_reported_clearly(monkeypatch, tmp_path):
    from app.instagram_content import video_frame_extraction

    monkeypatch.setattr(video_frame_extraction, "FFPROBE_BINARY", "ffprobe-does-not-exist")

    with pytest.raises(VideoFrameExtractionError, match="not installed"):
        video_frame_extraction.probe_duration_seconds(tmp_path / "clip.mp4")


# -- which frame reaches the single-image analyzer --------------------------


def test_the_representative_frame_is_the_middle_one_not_the_first():
    frames = [FrameSample(timestamp_seconds=t, image_base64="x", image_media_type="image/jpeg")
              for t in (1.0, 3.0, 5.0, 7.0, 9.0)]
    assert representative_frame(frames).timestamp_seconds == 5.0


def test_no_frames_is_an_error_not_a_crash():
    with pytest.raises(VideoFrameExtractionError, match="no frames"):
        representative_frame([])


# -- end to end through the ingest path -------------------------------------


@ffmpeg_required
def test_a_video_with_a_path_gets_a_real_analysis_and_ffprobes_duration(tmp_path, monkeypatch, caplog):
    """The whole point of this step: a video handed over as a path comes out
    of the pool with a real theme, real tags and a real duration -- not the
    placeholder that all 30 live videos are stuck on."""
    from datetime import datetime, timezone

    from app.instagram_content.analyze_and_ingest import analyze_and_ingest
    from app.instagram_content.captured_at_resolution import CapturedAtSource
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.media_pool_service import MediaPoolService
    from app.instagram_content.models import MediaType
    from app.instagram_content.vision_analysis import VisionAnalysisResult

    seen = {}

    class _StubAnalyzer:
        def analyze(self, **kwargs):
            seen.update(kwargs)
            return VisionAnalysisResult(
                theme="gym-mirror-selfie", tags=["gym", "motion"],
                aesthetic_score=0.74, reasoning="stub",
            )

    ingest_root = tmp_path / "ingest"
    ingest_root.mkdir()
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=640x360:rate=25:duration=6", "-pix_fmt", "yuv420p",
         str(ingest_root / "clip.mp4")],
        check=True, capture_output=True, timeout=60,
    )
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(ingest_root))

    service = MediaPoolService()
    service.reset()
    uploaded = datetime(2026, 9, 15, 19, 5, tzinfo=timezone.utc)

    with caplog.at_level(logging.WARNING):
        response = analyze_and_ingest(
            items=[MediaAnalyzeAndIngestItem(
                media_ref="drive-video-1", media_type=MediaType.video,
                video_path="clip.mp4",
                duration_seconds=30.0,  # wrong on purpose -- ffprobe must win
                upload_time=uploaded,
            )],
            analyzer=_StubAnalyzer(),
            pool_service=service,
        )

    assert response.failed == 0
    assert response.analyzed_and_ingested == 1

    stored = service.list_all()[0]
    assert stored.theme == "gym-mirror-selfie"
    assert stored.tags == ["gym", "motion"]
    assert stored.aesthetic_score == 0.74
    assert stored.duration_seconds == pytest.approx(6.0, abs=0.2), "ffprobe's value, not the 30.0 supplied"
    assert stored.captured_at == uploaded
    assert stored.captured_at_source is CapturedAtSource.upload_time
    assert stored.analysis_complete is True, "no longer a placeholder"

    assert seen["image_media_type"] == "image/jpeg"
    assert seen["image_base64"], "a real extracted frame reached the analyzer"
    assert any("duration mismatch" in r.getMessage() for r in caplog.records)
    assert "sampled frames" in response.results[0].reasoning
