from __future__ import annotations

import json

import httpx
import pytest

from app.instagram_content.caption_writer import AnthropicCaptionWriter, CaptionWriterConfig, CaptionWriterError
from app.instagram_content.media_pool_models import FinalizeDraftRequest, MediaPoolIngestRequest, MediaPoolItemCreate
from app.instagram_content.models import ContentStatus
from app.instagram_content.publisher import N8nInstagramPublisher
from app.instagram_content.service import InstagramContentError, InstagramContentService


def _anthropic_text_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def _image_create(ref, theme="desert-gold", score=0.75, tags=None):
    return MediaPoolItemCreate(media_ref=ref, media_type="image", theme=theme, aesthetic_score=score, tags=tags or [])


# -- AnthropicCaptionWriter: real, bounded API call --------------------------


def test_generate_fails_closed_without_an_api_key():
    writer = AnthropicCaptionWriter(config=CaptionWriterConfig(api_key=None))
    with pytest.raises(CaptionWriterError, match="ANTHROPIC_API_KEY is not set"):
        writer.generate("desert-gold", [], "carousel")


def test_generate_returns_the_model_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_text_response("Quiet mornings build the account. #tradingmindset #discipline #patience")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    caption = writer.generate("desert-gold", [], "single_image")
    assert "Quiet mornings" in caption


def test_generate_sends_the_real_api_key_and_model():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-api-key"] = request.headers.get("x-api-key")
        captured["body"] = json.loads(request.content)
        return _anthropic_text_response("Caption text. #tag1 #tag2 #tag3")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="sk-test-123", model="claude-sonnet-5"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    writer.generate("desert-gold", [], "reel")

    assert captured["x-api-key"] == "sk-test-123"
    assert captured["body"]["model"] == "claude-sonnet-5"
    assert "desert-gold" in captured["body"]["messages"][0]["content"]


def test_generate_raises_on_api_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid x-api-key")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="bad-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(CaptionWriterError, match="401"):
        writer.generate("desert-gold", [], "carousel")


def test_generate_raises_on_empty_text_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(CaptionWriterError, match="did not contain"):
        writer.generate("desert-gold", [], "carousel")


# -- finalize_draft: caption generation wired in, still fails closed --------


def _service_with_mocks(publisher_handler, caption_handler=None, api_key="test-key"):
    publisher = N8nInstagramPublisher(client=httpx.Client(transport=httpx.MockTransport(publisher_handler)))
    caption_writer = None
    if caption_handler is not None:
        caption_writer = AnthropicCaptionWriter(
            config=CaptionWriterConfig(api_key=api_key),
            client=httpx.Client(transport=httpx.MockTransport(caption_handler)),
        )
    return InstagramContentService(publisher=publisher, caption_writer=caption_writer)


def test_finalize_without_a_caption_generates_one_via_the_real_writer():
    from app.instagram_content import media_pool_service as pool_module

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool_module.media_pool_service.run_curation()[0]

    def caption_handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_text_response("Discipline compounds quietly. #tradingmindset #consistency #patience")

    service = _service_with_mocks(lambda r: httpx.Response(200, json={"media_id": "x"}), caption_handler)
    candidate = service.finalize_draft(draft.id)  # no request at all -- fully automated

    assert candidate.status == ContentStatus.proposed
    assert "Discipline compounds quietly" in candidate.caption_draft


def test_finalize_still_accepts_an_explicit_caption_and_skips_generation():
    from app.instagram_content import media_pool_service as pool_module

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool_module.media_pool_service.run_curation()[0]

    def caption_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("caption writer must not be called when caption_draft is explicitly provided")

    service = _service_with_mocks(lambda r: httpx.Response(200, json={"media_id": "x"}), caption_handler)
    candidate = service.finalize_draft(
        draft.id, FinalizeDraftRequest(caption_draft="My own caption. #tradingmindset #discipline #consistency")
    )
    assert candidate.caption_draft == "My own caption. #tradingmindset #discipline #consistency"


def test_finalize_fails_closed_when_caption_generation_fails():
    from app.instagram_content import media_pool_service as pool_module

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create(f"img-{i}") for i in range(4)]))
    draft = pool_module.media_pool_service.run_curation()[0]

    def caption_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    service = _service_with_mocks(lambda r: httpx.Response(200, json={"media_id": "x"}), caption_handler)
    with pytest.raises(InstagramContentError, match="Caption generation failed"):
        service.finalize_draft(draft.id)

    # photos must not be consumed on a failed generation attempt
    refreshed = pool_module.media_pool_service.get_draft(draft.id)
    assert refreshed.finalized is False
    for item_id in refreshed.media_item_ids:
        assert pool_module.media_pool_service.get(item_id).used is False
