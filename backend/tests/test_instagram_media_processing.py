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
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.instagram_content.media_processing import (
    RATIO_FEED,
    RATIO_REEL,
    MediaProcessingError,
    is_hdr,
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


def test_a_4k_video_is_shrunk_to_what_instagram_shows(tmp_path):
    """A 4K phone clip comes out at 1080x1920, not at full size -- measured
    on the file, the same shape, never stretched."""
    source = tmp_path / "uhd.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=2160x3840:rate=25:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        capture_output=True, check=True,
    )
    result = process_video(source)
    probe = _probe(result.path)
    assert (probe["width"], probe["height"]) == (1080, 1920)


def test_a_small_video_is_never_upscaled(source_video, tmp_path):
    small = tmp_path / "small.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=25:duration=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(small)],
        capture_output=True, check=True,
    )
    probe = _probe(process_video(small).path)
    assert (probe["width"], probe["height"]) == (720, 1280)


def _hlg_video(path: Path) -> Path:
    """Footage tagged the way an iPhone tags its HLG recordings."""
    subprocess.run(
        # setparams, not -color_trc: the output flags alone left the stream
        # tagged "unknown", which is not what an iPhone file looks like.
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=25:duration=1",
         "-vf", "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )
    return path


def test_hdr_footage_is_detected_from_the_file(tmp_path, source_video):
    assert is_hdr(_hlg_video(tmp_path / "hlg.mp4")) is True
    assert is_hdr(source_video) is False


def test_hdr_is_detected_the_way_a_real_iphone_file_reports_it(tmp_path, monkeypatch):
    """ffprobe prints "arib-std-b67," for an iPhone clip -- the trailing
    comma is its empty side-data list. The generated clip above has none, so
    it cannot catch this; the first real 4K video did."""
    from app.instagram_content import media_processing

    monkeypatch.setattr(
        media_processing, "_run",
        lambda command: subprocess.CompletedProcess(command, 0, b"arib-std-b67,\n", b""),
    )
    assert is_hdr(tmp_path / "any.mov") is True


def test_hdr_footage_comes_out_as_sdr(tmp_path):
    """The LUT is built for Rec.709. What leaves here must be SDR, checked
    on the output's own tags, and the flag must say so."""
    result = process_video(_hlg_video(tmp_path / "hlg.mp4"))
    assert result.tone_mapped is True
    assert is_hdr(result.path) is False


def test_sdr_footage_is_not_tone_mapped(source_video):
    assert process_video(source_video).tone_mapped is False


# -- the chain: does ingest actually produce a processed file? ---------------


def test_ingest_cuts_and_grades_while_the_file_is_still_there(tmp_path, monkeypatch):
    """The whole reason processing sits in the ingest step: the handed-over
    original lives in a directory the sweeper empties within a day, while a
    draft can wait for a decision far longer. If it does not happen here, it
    cannot happen at all.
    """
    import json as json_module

    import httpx

    from app.instagram_content.analyze_and_ingest import analyze_and_ingest
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.media_pool_service import MediaPoolService
    from app.instagram_content.vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisConfig

    ingest = tmp_path / "ingest"
    ingest.mkdir()
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(ingest))

    clip = ingest / "clip-1.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x1136:rate=25:duration=40",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
        capture_output=True, check=True,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json_module.dumps(
            {"theme": "gym-clip", "tags": ["gym"], "aesthetic_score": 0.8,
             "reasoning": "ok", "cover_timestamp_seconds": 5.0}
        )}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pool = MediaPoolService()
    pool.reset()

    response = analyze_and_ingest(
        [MediaAnalyzeAndIngestItem(
            media_ref="clip-1", media_type="video", video_path="clip-1.mp4", duration_seconds=40.0,
        )],
        AnthropicVisionAnalyzer(config=VisionAnalysisConfig(api_key="k"), client=client),
        pool,
        trim_analyzer=_FixedTrim(12.0, 30.0),
    )
    assert response.failed == 0

    item = pool.list_all()[0]
    assert item.processed_file == "clip-1.mp4", "the pool must point at the processed file"

    produced = Path(os.environ["JARVIS_PROCESSED_DIR"]) / item.processed_file
    assert produced.is_file()
    assert _probe(produced)["duration"] == pytest.approx(18.0, abs=0.5), "cut to the analyzed window"
    assert clip.is_file(), "the handed-over original must survive untouched"


class _FixedTrim:
    """Stands in for the trim analyzer -- the window is the input here, not
    what is being tested."""

    def __init__(self, start: float, end: float) -> None:
        self._start, self._end = start, end

    def analyze(self, frames, target_min, target_max):
        from app.instagram_content.media_pool_models import TrimAnalysisResult

        return TrimAnalysisResult(
            recommended_start_seconds=self._start,
            recommended_end_seconds=self._end,
            reasoning="fixed for the test",
        )


# -- photos: orientation, size, graded at ingest ------------------------------


def _photo_with_orientation(path: Path, size=(400, 200), orientation=6) -> Path:
    from PIL import Image

    image = Image.new("RGB", size, (200, 120, 40))
    exif = image.getexif()
    exif[0x0112] = orientation  # 6 = "rotate 90 CW to display", how an iPhone stores portrait shots
    image.save(path, format="JPEG", exif=exif.tobytes())
    return path


def test_a_photo_stored_sideways_comes_out_upright(tmp_path):
    """ffmpeg ignores the EXIF orientation flag; a portrait phone photo
    would otherwise be graded -- and posted -- lying on its side."""
    from PIL import Image

    result = process_image(_photo_with_orientation(tmp_path / "portrait.jpg"), ratio=None)
    assert Image.open(result.path).size == (200, 400)


def test_a_12mp_photo_is_capped_but_keeps_its_shape(tmp_path):
    source = tmp_path / "big.jpg"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=4032x3024", "-frames:v", "1", str(source)],
                   capture_output=True, check=True)
    from PIL import Image

    assert Image.open(process_image(source, ratio=None).path).size == (2560, 1920)


def test_ingest_grades_a_photo_from_its_original_bytes(tmp_path, monkeypatch):
    import base64
    import json as json_module

    import httpx

    from app.instagram_content.analyze_and_ingest import analyze_and_ingest
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.media_pool_service import MediaPoolService
    from app.instagram_content.vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisConfig

    photo = _photo_with_orientation(tmp_path / "p.jpg", size=(300, 200), orientation=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": json_module.dumps(
            {"theme": "beach", "tags": ["beach"], "aesthetic_score": 0.8, "reasoning": "ok"}
        )}]})

    pool = MediaPoolService()
    pool.reset()
    analyze_and_ingest(
        [MediaAnalyzeAndIngestItem(media_ref="photo-1", media_type="image",
                                   image_base64=base64.b64encode(photo.read_bytes()).decode(),
                                   image_media_type="image/jpeg")],
        AnthropicVisionAnalyzer(config=VisionAnalysisConfig(api_key="k"),
                                client=httpx.Client(transport=httpx.MockTransport(handler))),
        pool,
    )
    item = pool.list_all()[0]
    assert item.processed_file == "photo-1.jpg"
    assert (Path(os.environ["JARVIS_PROCESSED_DIR"]) / "photo-1.jpg").is_file()
    assert pool.pending_uploads().count == 1, "the graded photo must be queued for upload like a video"


# -- the finishing pass: exposure, structure, grain ---------------------------


def test_the_finishing_pass_runs_after_the_grade_and_in_order():
    """Exposure before structure before grain: sharpening a lifted shadow
    keeps what was rescued, and grain on top stays grain."""
    from app.instagram_content.media_processing import _build_video_filters

    chain = _build_video_filters(None, Path("/lut/INSTA.cube"))
    names = [f.split("=")[0] for f in chain]

    assert names == ["lut3d", "curves", "unsharp", "noise"]


def test_a_photo_really_comes_out_with_grain_and_more_structure(source_image, tmp_path):
    """Measured, not asserted on the command line: grain and sharpening both
    raise local variation, so the finished file is measurably less flat."""
    from PIL import Image, ImageStat

    from app.instagram_content.media_processing import _build_video_filters

    plain = tmp_path / "plain.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source_image), "-vf", ",".join(_build_video_filters(
            None, None, finish=False)) or "null", "-q:v", "2", str(plain)],
        capture_output=True, check=True,
    )
    finished = process_image(source_image, ratio=None, output_name="finished.jpg")

    def detail(path) -> float:
        with Image.open(path) as image:
            return ImageStat.Stat(image.convert("L").filter(
                __import__("PIL.ImageFilter", fromlist=["ImageFilter"]).FIND_EDGES)).mean[0]

    assert detail(finished.path) > detail(plain)
