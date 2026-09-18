"""Cutting, cropping and grading a real file with real ffmpeg.

Deliberately not mocked. The thing being tested is whether a file actually
comes out shorter and in the right shape -- a mocked ffmpeg would only prove
that the right string was assembled, which is precisely the kind of test
that passes while the feature does nothing. This project has already paid
twice for steps that reported success without doing anything, so these tests
generate genuine footage, run it through, and measure the result.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.instagram_content.media_processing import (
    RATIO_FEED,
    RATIO_REEL,
    MediaProcessingError,
    process_image,
    process_video,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed in this environment"
)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration": float(data["format"]["duration"]),
    }


@pytest.fixture
def source_video(tmp_path: Path) -> Path:
    """10 seconds of real 1080x1920 footage -- phone-shaped, so the crops
    below are the ones that happen in practice."""
    path = tmp_path / "source.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=25:duration=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture
def source_image(tmp_path: Path) -> Path:
    path = tmp_path / "source.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1600x1200", "-frames:v", "1", str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture(autouse=True)
def _output_dir(tmp_path, monkeypatch):
    out = tmp_path / "processed"
    monkeypatch.setenv("JARVIS_PROCESSED_DIR", str(out))
    monkeypatch.delenv("AURON_COLOR_LUT", raising=False)
    return out


# -- video ------------------------------------------------------------------


def test_a_video_is_really_cut_to_the_analyzed_window(source_video):
    """The window comes from the frame analysis. A cut that landed on the
    nearest keyframe instead would drift seconds away from what was chosen,
    which is why this re-encodes rather than stream-copying."""
    result = process_video(source_video, trim_start_seconds=2.0, trim_end_seconds=5.0)

    assert result.was_trimmed
    assert _probe(result.path)["duration"] == pytest.approx(3.0, abs=0.3)


def test_a_video_is_really_cropped_to_the_reel_ratio(source_video):
    result = process_video(source_video, ratio=RATIO_REEL)

    probed = _probe(result.path)
    assert probed["width"] / probed["height"] == pytest.approx(9 / 16, abs=0.01)


def test_a_video_can_be_cropped_to_the_feed_ratio_for_a_carousel(source_video):
    """A clip inside a carousel is a feed item, not a Reel -- 4:5, like the
    photos it sits between."""
    result = process_video(source_video, ratio=RATIO_FEED)

    probed = _probe(result.path)
    assert probed["width"] / probed["height"] == pytest.approx(4 / 5, abs=0.01)


def test_cropping_never_upscales(source_video):
    """A crop takes pixels away. Stretching to fill a ratio would distort
    the subject, which on a face is immediately visible."""
    source = _probe(source_video)
    result = process_video(source_video, ratio=RATIO_FEED)
    probed = _probe(result.path)

    assert probed["width"] <= source["width"]
    assert probed["height"] <= source["height"]


def test_the_source_file_is_never_modified(source_video):
    """The Drive original has to survive a bad grade or a wrong crop."""
    before = source_video.read_bytes()

    result = process_video(source_video, trim_start_seconds=1.0, trim_end_seconds=4.0)

    assert source_video.read_bytes() == before
    assert result.path != source_video


def test_a_video_without_a_trim_keeps_its_full_length(source_video):
    result = process_video(source_video, trim_start_seconds=None, trim_end_seconds=None)

    assert not result.was_trimmed
    assert _probe(result.path)["duration"] == pytest.approx(10.0, abs=0.3)


def test_audio_survives_the_processing(source_video):
    """Losing the audio track would be silent in both senses -- nothing
    would fail, the Reel would just be mute."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
         str(process_video(source_video, trim_start_seconds=1.0, trim_end_seconds=4.0).path)],
        capture_output=True, check=True,
    ).stdout
    assert any(s["codec_type"] == "audio" for s in json.loads(out)["streams"])


# -- refusals ---------------------------------------------------------------


def test_half_a_trim_window_is_refused(source_video):
    with pytest.raises(MediaProcessingError, match="both a start and an end"):
        process_video(source_video, trim_start_seconds=2.0)


def test_an_inverted_trim_window_is_refused(source_video):
    with pytest.raises(MediaProcessingError, match="must be after its start"):
        process_video(source_video, trim_start_seconds=5.0, trim_end_seconds=2.0)


def test_a_missing_source_is_refused_before_ffmpeg_runs(tmp_path):
    with pytest.raises(MediaProcessingError, match="no such video"):
        process_video(tmp_path / "gone.mp4")


# -- image ------------------------------------------------------------------


def test_a_photo_is_really_cropped_to_the_feed_ratio(source_image):
    result = process_image(source_image)

    probed = _probe(result.path)
    assert probed["width"] / probed["height"] == pytest.approx(4 / 5, abs=0.01)


def test_a_photo_and_a_video_get_the_same_crop_arithmetic(source_video, source_image):
    """One look across the account means one implementation. Two would
    drift, and a feed that reads as one feed is the entire point."""
    video = _probe(process_video(source_video, ratio=RATIO_FEED).path)
    image = _probe(process_image(source_image, ratio=RATIO_FEED).path)

    assert video["width"] / video["height"] == pytest.approx(image["width"] / image["height"], abs=0.01)


# -- grading ----------------------------------------------------------------


def test_without_a_lut_the_file_comes_back_honestly_ungraded(source_video):
    """No invented colour curves. Geometry and the cut still run."""
    result = process_video(source_video, trim_start_seconds=1.0, trim_end_seconds=3.0)

    assert result.graded is False
    assert result.was_trimmed


def test_a_lut_that_is_configured_but_missing_does_not_cost_the_cut(source_video, monkeypatch, tmp_path):
    """A moved colour file must not fail the whole operation -- losing a cut
    over it would be absurd."""
    monkeypatch.setenv("AURON_COLOR_LUT", str(tmp_path / "nowhere.cube"))

    result = process_video(source_video, trim_start_seconds=1.0, trim_end_seconds=3.0)

    assert result.graded is False
    assert _probe(result.path)["duration"] == pytest.approx(2.0, abs=0.3)


def test_a_real_lut_is_actually_applied(source_video, monkeypatch, tmp_path):
    """Proven by the pixels, not by a flag: this LUT inverts the image, so
    the output must differ from an ungraded run of the same input."""
    lut = tmp_path / "invert.cube"
    lut.write_text(
        "LUT_3D_SIZE 2\n"
        "1.0 1.0 1.0\n0.0 1.0 1.0\n1.0 0.0 1.0\n0.0 0.0 1.0\n"
        "1.0 1.0 0.0\n0.0 1.0 0.0\n1.0 0.0 0.0\n0.0 0.0 0.0\n"
    )
    plain = process_video(source_video, trim_start_seconds=0.0, trim_end_seconds=1.0,
                          output_name="plain.mp4")

    monkeypatch.setenv("AURON_COLOR_LUT", str(lut))
    graded = process_video(source_video, trim_start_seconds=0.0, trim_end_seconds=1.0,
                           output_name="graded.mp4")

    assert graded.graded is True
    assert graded.path.read_bytes() != plain.path.read_bytes()
