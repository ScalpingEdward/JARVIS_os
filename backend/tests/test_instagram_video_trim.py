from __future__ import annotations

import json

import httpx
import pytest

from app.instagram_content.edit_plan import build_edit_plan
from app.instagram_content.media_pool_models import FrameSample
from app.instagram_content.models import MediaItem, PostFormat
from app.instagram_content.video_trim_analysis import (
    AnthropicVideoTrimAnalyzer,
    VideoTrimAnalysisConfig,
    VideoTrimAnalysisError,
)


def _frames(count=6, start=0.0, step=20.0):
    return [FrameSample(timestamp_seconds=start + i * step, image_url=f"https://example.com/frame{i}.jpg") for i in range(count)]


def _trim_response(start: float, end: float, reasoning: str = "Strongest hook here.") -> httpx.Response:
    payload = {"recommended_start_seconds": start, "recommended_end_seconds": end, "reasoning": reasoning}
    return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(payload)}]})


# -- AnthropicVideoTrimAnalyzer -----------------------------------------------


def test_analyze_fails_closed_without_an_api_key():
    analyzer = AnthropicVideoTrimAnalyzer(config=VideoTrimAnalysisConfig(api_key=None))
    with pytest.raises(VideoTrimAnalysisError, match="ANTHROPIC_API_KEY is not set"):
        analyzer.analyze(_frames(), 15, 30)


def test_analyze_requires_at_least_three_frames():
    analyzer = AnthropicVideoTrimAnalyzer(config=VideoTrimAnalysisConfig(api_key="test-key"))
    with pytest.raises(VideoTrimAnalysisError, match="At least 3"):
        analyzer.analyze(_frames(count=2), 15, 30)


def test_analyze_returns_a_window_within_the_sampled_range():
    def handler(request: httpx.Request) -> httpx.Response:
        return _trim_response(40.0, 65.0)

    analyzer = AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = analyzer.analyze(_frames(count=6, start=0.0, step=20.0), 15, 30)  # frames span 0-100s
    assert result.recommended_start_seconds == pytest.approx(40.0)
    assert result.recommended_end_seconds == pytest.approx(65.0)


def test_analyze_sends_every_frame_labeled_with_its_real_timestamp():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _trim_response(10.0, 25.0)

    analyzer = AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    analyzer.analyze(_frames(count=4, start=0.0, step=10.0), 15, 30)

    content = captured["body"]["messages"][0]["content"]
    image_blocks = [b for b in content if b["type"] == "image"]
    assert len(image_blocks) == 4
    text_labels = [b["text"] for b in content if b["type"] == "text" and "frame at" in b.get("text", "")]
    assert "0.0s" in text_labels[0]
    assert "30.0s" in text_labels[-1]


def test_analyze_rejects_a_window_outside_the_sampled_range():
    """The critical safety property: a hallucinated timestamp outside what
    was actually sampled must be treated as a bad response, not clamped."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _trim_response(500.0, 530.0)  # frames only span 0-100s

    analyzer = AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VideoTrimAnalysisError, match="outside the sampled range"):
        analyzer.analyze(_frames(count=6, start=0.0, step=20.0), 15, 30)


def test_analyze_rejects_end_before_start():
    def handler(request: httpx.Request) -> httpx.Response:
        return _trim_response(60.0, 40.0)

    analyzer = AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VideoTrimAnalysisError, match="<="):
        analyzer.analyze(_frames(count=6, start=0.0, step=20.0), 15, 30)


def test_analyze_raises_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not json"}]})

    analyzer = AnthropicVideoTrimAnalyzer(
        config=VideoTrimAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VideoTrimAnalysisError, match="not valid JSON"):
        analyzer.analyze(_frames(count=6, start=0.0, step=20.0), 15, 30)


# -- edit_plan.py: uses a real recommendation when present, never invents ---


def test_edit_plan_uses_a_real_recommended_trim_window():
    item = MediaItem(
        media_ref="clip-1",
        media_type="video",
        aesthetic_score=0.8,
        duration_seconds=120.0,
        recommended_trim_start_seconds=40.0,
        recommended_trim_end_seconds=65.0,
    )
    plan = build_edit_plan([item], PostFormat.reel)
    assert plan[0].trim_needed is True
    assert plan[0].trim_start_seconds == pytest.approx(40.0)
    assert plan[0].trim_end_seconds == pytest.approx(65.0)
    assert "analyzed sampled frames" in plan[0].notes


def test_edit_plan_leaves_trim_window_unset_without_a_real_analysis():
    item = MediaItem(media_ref="clip-2", media_type="video", aesthetic_score=0.8, duration_seconds=120.0)
    plan = build_edit_plan([item], PostFormat.reel)
    assert plan[0].trim_needed is True
    assert plan[0].trim_start_seconds is None
    assert plan[0].trim_end_seconds is None


# -- media pool service: storing the recommendation -------------------------


def test_set_trim_recommendation_persists_on_the_pool_item():
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate
    from app.instagram_content.media_pool_service import MediaPoolService

    pool = MediaPoolService()
    pool.ingest(
        MediaPoolIngestRequest(
            items=[MediaPoolItemCreate(media_ref="clip-1", media_type="video", theme="t", aesthetic_score=0.8, duration_seconds=120.0)]
        )
    )
    item_id = pool.list_available()[0].id

    updated = pool.set_trim_recommendation(item_id, 40.0, 65.0, "Strongest hook.")
    assert updated.recommended_trim_start_seconds == pytest.approx(40.0)
    assert pool.get(item_id).recommended_trim_end_seconds == pytest.approx(65.0)
