from __future__ import annotations

import json

import httpx
import pytest

from app.instagram_content.analyze_and_ingest import analyze_and_ingest
from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.vision_analysis import AnthropicVisionAnalyzer, VisionAnalysisConfig, VisionAnalysisError


def _vision_response(theme="desert-gold", tags=None, score=0.8, reasoning="Clean composition."):
    body = {"theme": theme, "tags": tags or ["gold", "desert"], "aesthetic_score": score, "reasoning": reasoning}
    return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(body)}]})


# -- AnthropicVisionAnalyzer: real, bounded vision call ----------------------


def test_analyze_fails_closed_without_an_api_key():
    analyzer = AnthropicVisionAnalyzer(config=VisionAnalysisConfig(api_key=None))
    with pytest.raises(VisionAnalysisError, match="ANTHROPIC_API_KEY is not set"):
        analyzer.analyze(image_base64="abc", image_media_type="image/jpeg")


def test_analyze_requires_an_image_source():
    analyzer = AnthropicVisionAnalyzer(config=VisionAnalysisConfig(api_key="test-key"))
    with pytest.raises(VisionAnalysisError, match="image_base64.*or image_url"):
        analyzer.analyze()


def test_analyze_returns_the_parsed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return _vision_response(theme="mystic-symbol", tags=["gold", "symbol"], score=0.72, reasoning="Warm tones, minimal.")

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")
    assert result.theme == "mystic-symbol"
    assert result.tags == ["gold", "symbol"]
    assert result.aesthetic_score == pytest.approx(0.72)
    assert "Warm tones" in result.reasoning


def test_analyze_sends_the_real_image_bytes_and_criteria():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _vision_response()

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")

    content = captured["body"]["messages"][0]["content"]
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["data"] == "ZmFrZQ=="
    assert image_block["source"]["media_type"] == "image/jpeg"


def test_analyze_accepts_an_image_url_instead_of_base64():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        image_block = next(b for b in body["messages"][0]["content"] if b["type"] == "image")
        assert image_block["source"] == {"type": "url", "url": "https://example.com/photo.jpg"}
        return _vision_response()

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = analyzer.analyze(image_url="https://example.com/photo.jpg")
    assert result.theme


def test_analyze_tolerates_markdown_fenced_json():
    def handler(request: httpx.Request) -> httpx.Response:
        fenced = "```json\n" + json.dumps({"theme": "x", "tags": [], "aesthetic_score": 0.5, "reasoning": "ok"}) + "\n```"
        return httpx.Response(200, json={"content": [{"type": "text", "text": fenced}]})

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")
    assert result.theme == "x"


def test_analyze_rejects_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not json at all"}]})

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VisionAnalysisError, match="not valid JSON"):
        analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")


def test_analyze_rejects_an_out_of_range_score():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"theme": "x", "tags": [], "aesthetic_score": 1.5, "reasoning": "bad"}
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(body)}]})

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VisionAnalysisError, match="aesthetic_score"):
        analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")


def test_analyze_raises_on_api_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid x-api-key")

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="bad-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(VisionAnalysisError, match="401"):
        analyzer.analyze(image_base64="ZmFrZQ==", image_media_type="image/jpeg")


# -- analyze_and_ingest: batch orchestration, per-item failure isolation ----


def test_analyze_and_ingest_a_successful_batch():
    def handler(request: httpx.Request) -> httpx.Response:
        return _vision_response(theme="desert-gold", score=0.8)

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    items = [
        MediaAnalyzeAndIngestItem(media_ref=f"img-{i}", media_type="image", image_base64="ZmFrZQ==", image_media_type="image/jpeg")
        for i in range(3)
    ]
    response = analyze_and_ingest(items, analyzer, pool)

    assert response.analyzed_and_ingested == 3
    assert response.failed == 0
    assert all(r.success for r in response.results)
    assert len(pool.list_available()) == 3
    assert pool.list_available()[0].theme == "desert-gold"


def test_analyze_and_ingest_video_without_duration_fails_that_item_only():
    def handler(request: httpx.Request) -> httpx.Response:
        return _vision_response()

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    items = [
        MediaAnalyzeAndIngestItem(media_ref="good", media_type="image", image_base64="ZmFrZQ==", image_media_type="image/jpeg"),
        MediaAnalyzeAndIngestItem(media_ref="bad-video", media_type="video", image_base64="ZmFrZQ==", image_media_type="image/jpeg"),
    ]
    response = analyze_and_ingest(items, analyzer, pool)

    assert response.analyzed_and_ingested == 1
    assert response.failed == 1
    bad_result = next(r for r in response.results if r.media_ref == "bad-video")
    assert not bad_result.success
    assert "duration_seconds" in bad_result.error


def test_analyze_and_ingest_one_failed_analysis_does_not_block_the_rest():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(500, text="upstream error")
        return _vision_response()

    analyzer = AnthropicVisionAnalyzer(
        config=VisionAnalysisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pool = MediaPoolService()
    items = [
        MediaAnalyzeAndIngestItem(media_ref="fails", media_type="image", image_base64="ZmFrZQ==", image_media_type="image/jpeg"),
        MediaAnalyzeAndIngestItem(media_ref="succeeds", media_type="image", image_base64="ZmFrZQ==", image_media_type="image/jpeg"),
    ]
    response = analyze_and_ingest(items, analyzer, pool)

    assert response.analyzed_and_ingested == 1
    assert response.failed == 1
    assert len(pool.list_available()) == 1
    assert pool.list_available()[0].media_ref == "succeeds"


def test_analyze_and_ingest_via_the_api(monkeypatch):
    from fastapi.testclient import TestClient

    from app.instagram_content import api as instagram_api
    from app.instagram_content.media_pool_service import media_pool_service
    from app.main import app

    media_pool_service.reset()

    def fake_analyzer(*args, **kwargs):
        class _Fake:
            def analyze(self, **kw):
                from app.instagram_content.vision_analysis import VisionAnalysisResult

                return VisionAnalysisResult(theme="desert-gold", tags=["gold"], aesthetic_score=0.8, reasoning="ok")

        return _Fake()

    monkeypatch.setattr(instagram_api, "AnthropicVisionAnalyzer", fake_analyzer)

    client = TestClient(app)
    response = client.post(
        "/v1/instagram/media-pool/analyze-and-ingest",
        json={"items": [{"media_ref": "api-img-1", "media_type": "image", "image_base64": "ZmFrZQ==", "image_media_type": "image/jpeg"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed_and_ingested"] == 1
    assert body["results"][0]["theme"] == "desert-gold"
