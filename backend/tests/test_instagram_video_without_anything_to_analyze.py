"""A video with nothing to analyze must say so, not report success.

This closes the third instance of the same failure mode in this system:

  1. the n8n pre-filter treated "in the pool" as "done", so 30 placeholder
     videos were dropped from every run and could never improve;
  2. a truncated +faststart handover kept its moov atom, so ffprobe read the
     full duration off half a file and reported it confidently;
  3. and this one -- the first real handover run passed 29 videos whose
     video_path had been silently dropped by an upstream node. Every item
     came back success=true with analyzed_and_ingested 0. The pool looked
     untouched and nothing anywhere said why.

Each time something impossible happened and the system reported success.
Writing a placeholder entry was a stopgap for the period before frame
extraction existed; keeping it now means an unanalyzable video is
indistinguishable from an analyzed one that yielded nothing.
"""

import pytest

from app.instagram_content.analyze_and_ingest import analyze_and_ingest
from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import MediaType
from app.instagram_content.vision_analysis import VisionAnalysisResult


class _StubAnalyzer:
    def __init__(self):
        self.called = False

    def analyze(self, **kwargs):
        self.called = True
        return VisionAnalysisResult(
            theme="gym-mirror-selfie", tags=["gym"], aesthetic_score=0.7, reasoning="stub"
        )


@pytest.fixture
def service():
    pool = MediaPoolService()
    pool.reset()
    return pool


def _video(**overrides) -> MediaAnalyzeAndIngestItem:
    payload = dict(media_ref="drive-video-1", media_type=MediaType.video, duration_seconds=9.3)
    payload.update(overrides)
    return MediaAnalyzeAndIngestItem(**payload)


def test_a_video_with_no_path_and_no_image_fails_loudly(service):
    analyzer = _StubAnalyzer()

    response = analyze_and_ingest(items=[_video()], analyzer=analyzer, pool_service=service)

    assert response.failed == 1
    assert response.analyzed_and_ingested == 0
    result = response.results[0]
    assert result.success is False
    assert "neither video_path nor an image" in result.error
    assert analyzer.called is False


def test_nothing_is_written_to_the_pool(service):
    """The decisive part. Previously this wrote a placeholder -- theme
    "video", no tags, score 0.6 -- which is exactly what 30 rows in the live
    pool still are."""
    analyze_and_ingest(items=[_video()], analyzer=_StubAnalyzer(), pool_service=service)

    assert service.list_all() == []


def test_it_does_not_quietly_pass_as_a_duplicate_either(service):
    """The precise shape of the live failure: an unanalyzable video whose
    media_ref is already in the pool used to produce an identical placeholder,
    which ingest() then skipped as a duplicate -- 0 ingested, 0 failed, and a
    response that claimed everything was fine."""
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate

    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="video",
        tags=[], aesthetic_score=0.6, duration_seconds=9.3,
    )]))

    response = analyze_and_ingest(items=[_video()], analyzer=_StubAnalyzer(), pool_service=service)

    assert response.failed == 1, "0 failed is what hid this for a whole run"
    assert response.results[0].success is False


def test_the_existing_entry_is_left_exactly_as_it_was(service):
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate

    service.ingest(MediaPoolIngestRequest(items=[MediaPoolItemCreate(
        media_ref="drive-video-1", media_type=MediaType.video, theme="video",
        tags=[], aesthetic_score=0.6, duration_seconds=9.3,
    )]))
    before = service.list_all()[0]

    analyze_and_ingest(items=[_video()], analyzer=_StubAnalyzer(), pool_service=service)

    after = service.list_all()[0]
    assert after.id == before.id
    assert after.analyzed_at == before.analyzed_at
    assert len(service.list_all()) == 1


def test_a_video_with_a_thumbnail_is_still_analyzed_normally(service):
    """Only the empty case is refused. A caller that supplies a still frame
    has given AURON something real to look at."""
    analyzer = _StubAnalyzer()

    response = analyze_and_ingest(
        items=[_video(image_base64="ZmFrZQ==", image_media_type="image/jpeg")],
        analyzer=analyzer,
        pool_service=service,
    )

    assert response.failed == 0
    assert response.analyzed_and_ingested == 1
    assert analyzer.called is True
    assert service.list_all()[0].theme == "gym-mirror-selfie"


def test_a_video_with_an_image_url_is_also_still_analyzed(service):
    response = analyze_and_ingest(
        items=[_video(image_url="https://example.invalid/frame.jpg")],
        analyzer=_StubAnalyzer(),
        pool_service=service,
    )

    assert response.failed == 0
    assert response.analyzed_and_ingested == 1


def test_one_unanalyzable_video_does_not_take_the_batch_with_it(service):
    response = analyze_and_ingest(
        items=[
            _video(media_ref="nothing-to-see"),
            MediaAnalyzeAndIngestItem(
                media_ref="a-photo", media_type=MediaType.image,
                image_base64="ZmFrZQ==", image_media_type="image/jpeg",
            ),
        ],
        analyzer=_StubAnalyzer(),
        pool_service=service,
    )

    by_ref = {r.media_ref: r for r in response.results}
    assert by_ref["nothing-to-see"].success is False
    assert by_ref["a-photo"].success is True
    assert response.failed == 1
    assert response.analyzed_and_ingested == 1


def test_a_video_without_a_duration_still_fails_on_that_first(service):
    """The duration check stays ahead of this one, so its message keeps
    naming the actual problem rather than the more general one."""
    response = analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(media_ref="v", media_type=MediaType.video)],
        analyzer=_StubAnalyzer(),
        pool_service=service,
    )

    assert response.results[0].success is False
    assert "duration_seconds is required" in response.results[0].error
