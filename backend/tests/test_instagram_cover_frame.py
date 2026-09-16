"""Picking the Reel cover, and using one set of frames for everything.

The cover is the single frame someone sees before deciding whether to watch.
The Graph API's thumb_offset defaults to 0, so a video without an explicit
cover gets its opening frame -- on phone footage regularly black, blurred or
mid-movement. Every reel published so far got exactly that.

Frames are sampled once per ingest and handed to the vision analysis, the
cover choice and the trim window together. Not just for speed: sampling per
step would drift apart the moment anyone touched the sampling parameters,
and the cover would end up on a frame the analysis never saw. It is also the
only opportunity -- n8n deletes the file once the ingest succeeds.
"""

import logging
import shutil
import subprocess

import pytest

from app.instagram_content.analyze_and_ingest import (
    _choose_cover_timestamp,
    _trim_window,
)
from app.instagram_content.media_pool_models import (
    FrameSample,
    MediaPoolItemCreate,
    TrimAnalysisResult,
)
from app.instagram_content.models import MediaType
from app.instagram_content.reel_targets import (
    DEFAULT_TARGET_MAX_SECONDS,
    DEFAULT_TARGET_MIN_SECONDS,
    needs_trim,
    target_max_seconds,
    target_min_seconds,
)
from app.instagram_content.vision_analysis import (
    AnthropicVisionAnalyzer,
    VisionAnalysisConfig,
    VisionAnalysisError,
    VisionAnalysisResult,
)

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed here (they ship in the api image)",
)


def _frames(*timestamps: float) -> list[FrameSample]:
    return [
        FrameSample(timestamp_seconds=t, image_base64="ZmFrZQ==", image_media_type="image/jpeg")
        for t in timestamps
    ]


def _analysis(cover: float | None = None) -> VisionAnalysisResult:
    return VisionAnalysisResult(
        theme="gym-mirror-selfie", tags=["gym"], aesthetic_score=0.7,
        reasoning="stub", cover_timestamp_seconds=cover,
    )


# -- the target length is configuration, not a constant ---------------------


def test_the_target_length_defaults_are_the_documented_ones():
    assert target_min_seconds() == DEFAULT_TARGET_MIN_SECONDS
    assert target_max_seconds() == DEFAULT_TARGET_MAX_SECONDS


def test_the_target_length_can_be_changed_without_touching_code(monkeypatch):
    """What counts as too long follows the content strategy, so it has to be
    settable from outside."""
    monkeypatch.setenv("AURON_REEL_TARGET_MAX_SECONDS", "12")
    assert target_max_seconds() == 12.0
    assert needs_trim(15.0) is True
    assert needs_trim(9.3) is False


def test_only_a_video_past_the_target_needs_trimming():
    assert needs_trim(45.95) is True
    assert needs_trim(28.67) is False
    assert needs_trim(30.0) is False, "exactly at the target is not over it"


def test_a_nonsense_configured_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("AURON_REEL_TARGET_MAX_SECONDS", "not-a-number")
    assert target_max_seconds() == DEFAULT_TARGET_MAX_SECONDS
    monkeypatch.setenv("AURON_REEL_TARGET_MAX_SECONDS", "-5")
    assert target_max_seconds() == DEFAULT_TARGET_MAX_SECONDS


# -- the cover fallback chain -----------------------------------------------


def test_the_models_choice_wins():
    cover = _choose_cover_timestamp(_analysis(cover=7.5), None, _frames(1.0, 4.0, 7.5, 11.0))
    assert cover == 7.5


def test_without_a_choice_the_trim_start_is_used():
    """Where the Reel actually begins is the frame a viewer sees first."""
    trim = TrimAnalysisResult(recommended_start_seconds=12.0, recommended_end_seconds=30.0, reasoning="x")
    assert _choose_cover_timestamp(_analysis(cover=None), trim, _frames(1.0, 12.0, 30.0)) == 12.0


def test_with_neither_the_middle_frame_is_used_never_the_first():
    frames = _frames(1.0, 4.0, 7.0, 10.0, 13.0)
    cover = _choose_cover_timestamp(_analysis(cover=None), None, frames)
    assert cover == 7.0
    assert cover != frames[0].timestamp_seconds


def test_a_video_never_ends_up_without_a_cover():
    """The whole reason the chain has a third step: None would mean
    thumb_offset defaults to 0, which is the frame we are trying to avoid."""
    for trim in (None, TrimAnalysisResult(recommended_start_seconds=2.0, recommended_end_seconds=9.0, reasoning="x")):
        for cover in (None, 4.0):
            result = _choose_cover_timestamp(_analysis(cover=cover), trim, _frames(1.0, 4.0, 7.0))
            assert result is not None and result > 0


# -- the model may not invent a timestamp -----------------------------------


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: str):
        self._payload = payload

    def json(self):
        return {"content": [{"type": "text", "text": self._payload}]}


class _FakeClient:
    def __init__(self, payload: str):
        self._payload = payload
        self.sent = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.sent = json
        return _FakeResponse(self._payload)

    def close(self):
        pass


def _analyzer(payload: str) -> tuple[AnthropicVisionAnalyzer, _FakeClient]:
    client = _FakeClient(payload)
    return AnthropicVisionAnalyzer(config=VisionAnalysisConfig(api_key="test-key"), client=client), client


def test_a_cover_timestamp_that_was_actually_offered_is_accepted():
    analyzer, client = _analyzer(
        '{"theme": "gym", "tags": ["a"], "aesthetic_score": 0.8, '
        '"cover_timestamp_seconds": 4.0, "reasoning": "r"}'
    )
    result = analyzer.analyze(frames=_frames(1.0, 4.0, 7.0))

    assert result.cover_timestamp_seconds == 4.0
    assert result.theme == "gym"
    images = [b for b in client.sent["messages"][0]["content"] if b.get("type") == "image"]
    assert len(images) == 3, "every frame reached the model, not just one"


def test_a_cover_timestamp_the_model_was_never_shown_is_dropped(caplog):
    """Same rule the trim analyzer applies to its window: an unoffered
    timestamp is a bad response, not something to snap to a neighbour. The
    rest of the analysis is still good, so only the cover is discarded."""
    analyzer, _ = _analyzer(
        '{"theme": "gym", "tags": ["a"], "aesthetic_score": 0.8, '
        '"cover_timestamp_seconds": 5.5, "reasoning": "r"}'
    )
    with caplog.at_level(logging.WARNING):
        result = analyzer.analyze(frames=_frames(1.0, 4.0, 7.0))

    assert result.cover_timestamp_seconds is None
    assert result.theme == "gym", "the rest of the analysis survives"
    assert any("not shown" in r.getMessage() for r in caplog.records)


def test_a_missing_cover_is_not_an_error():
    analyzer, _ = _analyzer('{"theme": "gym", "tags": ["a"], "aesthetic_score": 0.8, "reasoning": "r"}')
    assert analyzer.analyze(frames=_frames(1.0, 4.0)).cover_timestamp_seconds is None


def test_a_broken_analysis_still_fails_loudly():
    analyzer, _ = _analyzer('{"tags": [], "aesthetic_score": 0.8}')
    with pytest.raises(VisionAnalysisError, match="theme"):
        analyzer.analyze(frames=_frames(1.0, 4.0))


def test_a_photo_still_goes_through_the_single_image_path():
    analyzer, client = _analyzer(
        '{"theme": "desk", "tags": ["a"], "aesthetic_score": 0.6, "reasoning": "r"}'
    )
    result = analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")

    assert result.cover_timestamp_seconds is None
    images = [b for b in client.sent["messages"][0]["content"] if b.get("type") == "image"]
    assert len(images) == 1


# -- storage ----------------------------------------------------------------


def test_a_cover_past_the_end_of_the_video_is_refused():
    with pytest.raises(ValueError, match="past the end"):
        MediaPoolItemCreate(
            media_ref="v1", media_type=MediaType.video, theme="gym", tags=["a"],
            aesthetic_score=0.7, duration_seconds=9.3, cover_timestamp_seconds=12.0,
        )


def test_a_photo_cannot_carry_a_cover_timestamp():
    with pytest.raises(ValueError, match="only meaningful for video"):
        MediaPoolItemCreate(
            media_ref="i1", media_type=MediaType.image, theme="gym", tags=["a"],
            aesthetic_score=0.7, cover_timestamp_seconds=4.0,
        )


def test_the_cover_reaches_the_media_item_that_n8n_receives():
    """Without this hop cover_timestamp_seconds is a number with no consumer:
    n8n only ever sees MediaItem."""
    from app.instagram_content.models import MediaItem

    item = MediaItem(
        media_ref="v1", media_type=MediaType.video, aesthetic_score=0.7,
        duration_seconds=9.3, cover_timestamp_seconds=4.0,
    )
    assert item.model_dump(mode="json")["cover_timestamp_seconds"] == 4.0
    assert round(item.cover_timestamp_seconds * 1000) == 4000, "thumb_offset is milliseconds"


# -- trim only above the target, on the same frames --------------------------


class _StubTrimAnalyzer:
    def __init__(self):
        self.seen_frames = None
        self.seen_targets = None

    def analyze(self, frames, target_min_seconds, target_max_seconds):
        self.seen_frames = frames
        self.seen_targets = (target_min_seconds, target_max_seconds)
        return TrimAnalysisResult(
            recommended_start_seconds=frames[1].timestamp_seconds,
            recommended_end_seconds=frames[-1].timestamp_seconds,
            reasoning="stub",
        )


def test_a_video_within_the_target_is_not_trim_analyzed():
    stub = _StubTrimAnalyzer()
    assert _trim_window(_frames(1.0, 5.0, 9.0), 9.3, stub, "v1") is None
    assert stub.seen_frames is None, "no call spent on a video that needs no cut"


def test_an_over_length_video_is_trim_analyzed_on_the_very_same_frames():
    frames = _frames(2.3, 12.0, 24.0, 36.0, 43.6)
    stub = _StubTrimAnalyzer()

    trim = _trim_window(frames, 45.95, stub, "v1")

    assert trim is not None
    assert stub.seen_frames is frames, "the frames already sampled, not a fresh extraction"
    assert stub.seen_targets == (target_min_seconds(), target_max_seconds())


def test_a_failing_trim_analysis_does_not_lose_the_item(caplog):
    from app.instagram_content.video_trim_analysis import VideoTrimAnalysisError

    class _Failing:
        def analyze(self, *args):
            raise VideoTrimAnalysisError("model said no")

    with caplog.at_level(logging.WARNING):
        assert _trim_window(_frames(1.0, 20.0, 40.0), 45.95, _Failing(), "v1") is None
    assert any("trim analysis failed" in r.getMessage() for r in caplog.records)


# -- end to end --------------------------------------------------------------


@ffmpeg_required
def test_one_extraction_feeds_analysis_cover_and_trim(tmp_path, monkeypatch):
    """The reuse itself: a single sample_video() call, and the cover the model
    picks is provably one of the frames the analysis was run on."""
    from app.instagram_content import analyze_and_ingest as module
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.media_pool_service import MediaPoolService

    ingest_root = tmp_path / "ingest"
    ingest_root.mkdir()
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=640x360:rate=25:duration=40", "-pix_fmt", "yuv420p",
         str(ingest_root / "long.mp4")],
        check=True, capture_output=True, timeout=120,
    )
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(ingest_root))

    extractions = []
    original = module.sample_video

    def _counting_sample_video(path, **kwargs):
        result = original(path, **kwargs)
        extractions.append(result[1])
        return result

    monkeypatch.setattr(module, "sample_video", _counting_sample_video)

    class _StubVision:
        def analyze(self, **kwargs):
            frames = kwargs["frames"]
            return VisionAnalysisResult(
                theme="testsrc-pattern", tags=["synthetic"], aesthetic_score=0.5,
                reasoning="stub", cover_timestamp_seconds=frames[2].timestamp_seconds,
            )

    trim_stub = _StubTrimAnalyzer()
    service = MediaPoolService()
    service.reset()

    response = module.analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(
            media_ref="drive-long", media_type=MediaType.video, video_path="long.mp4",
        )],
        analyzer=_StubVision(),
        pool_service=service,
        trim_analyzer=trim_stub,
    )

    assert response.failed == 0
    assert len(extractions) == 1, "frames were sampled exactly once"
    frames = extractions[0]

    stored = service.list_all()[0]
    assert stored.cover_timestamp_seconds == frames[2].timestamp_seconds
    assert stored.cover_timestamp_seconds in [f.timestamp_seconds for f in frames]
    assert stored.recommended_trim_start_seconds == frames[1].timestamp_seconds
    assert stored.recommended_trim_end_seconds == frames[-1].timestamp_seconds
    assert trim_stub.seen_frames is frames, "trim ran on the same frames, not a second extraction"
    assert "cover at" in response.results[0].reasoning
