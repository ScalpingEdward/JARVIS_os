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
        return _anthropic_text_response("Quiet mornings build the account. #trading #discipline #mindset")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    caption = writer.generate("desert-gold", [], "single_image")
    assert "Quiet mornings" in caption


def test_a_caption_without_hashtags_gets_one_corrective_retry():
    """The first real card went out with no hashtags although the prompt
    demanded 3-5. The count is checked, and the retry says what was wrong."""
    prompts: list[str] = []
    answers = iter(["Nobody claps at the top of a mountain.", "Nobody claps. #trading #discipline #mindset"])

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["messages"][0]["content"])
        return _anthropic_text_response(next(answers))

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="k"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert writer.generate("t", [], "carousel").endswith("#mindset")
    assert len(prompts) == 2
    assert "contained 0 hashtags" in prompts[1]


def test_a_caption_that_misses_the_hashtag_range_twice_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_text_response(
            "Text. #trading #forex #gym #travel #portrait #mindset #discipline")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="k"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(CaptionWriterError, match="7 hashtags"):
        writer.generate("t", [], "carousel")


def test_count_hashtags_ignores_things_that_only_look_like_one():
    from app.instagram_content.caption_writer import count_hashtags

    assert count_hashtags("Level #1 kept. #trading #gym\n#food") == 4
    assert count_hashtags("mail me: a#b, C# ist eine Sprache, ##") == 0


def test_generate_sends_the_real_api_key_and_model():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-api-key"] = request.headers.get("x-api-key")
        captured["body"] = json.loads(request.content)
        return _anthropic_text_response("Caption text. #trading #forex #mindset")

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
        return _anthropic_text_response("Discipline compounds quietly. #trading #tradingpsychology #discipline")

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


def test_invented_hashtags_are_rejected_and_named_in_the_retry():
    """#QuietWealth and #StillWaters read well and are browsed by nobody --
    the second real card went out with five of them."""
    prompts: list[str] = []
    answers = iter([
        "Built quietly. #QuietWealth #StillWaters #discipline",
        "Built quietly. #trading #discipline #mindset",
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["messages"][0]["content"])
        return _anthropic_text_response(next(answers))

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="k"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    caption = writer.generate("t", [], "carousel")

    assert caption.endswith("#trading #discipline #mindset")
    assert "#QuietWealth #StillWaters" in prompts[1]
    assert "#trading" in prompts[0], "the allowed list is part of the first prompt already"


def test_the_same_hashtag_twice_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_text_response("Text. #trading #trading #Trading")

    writer = AnthropicCaptionWriter(
        config=CaptionWriterConfig(api_key="k"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(CaptionWriterError, match="repeated the same hashtag"):
        writer.generate("t", [], "carousel")


def test_the_allowed_list_covers_every_pillar_and_holds_no_duplicates():
    from app.instagram_content.hashtags import ALLOWED, ALLOWED_BY_PILLAR

    assert set(ALLOWED_BY_PILLAR) == {"trading", "gym", "food", "travel", "portrait"}
    flat = [tag for tags in ALLOWED_BY_PILLAR.values() for tag in tags]
    assert len(flat) == len(set(flat)), "a tag listed under two pillars would be maintained twice"
    assert all(tag == tag.lower() and tag.startswith("#") for tag in ALLOWED)


def test_publishing_sends_the_processed_file_not_the_phone_original():
    """Every edit -- cut, grade, exposure, crop -- lives in the processed
    file. Posting media_ref would have quietly undone all of it."""
    from app.instagram_content import media_pool_service as pool_module
    from app.instagram_content.media_pool_models import ProcessedUploadedRequest
    from app.instagram_content.models import ContentCandidateCreate, ContentDecision, MediaItem

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create("orig-1")]))
    pool_module.media_pool_service.set_processed_file("orig-1", "orig-1.jpg")
    pool_module.media_pool_service.record_processed_uploads(ProcessedUploadedRequest(
        items=[{"media_ref": "orig-1", "processed_media_ref": "drive-processed-1"}]))

    seen: dict = {}

    def publisher_handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"media_id": "ig-1"})

    service = _service_with_mocks(publisher_handler)
    service.reset()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="orig-1", media_type="image", aesthetic_score=0.8)],
        caption_draft="Quiet. #trading #discipline #mindset",
    ))
    service.decide(candidate.id, ContentDecision(approved=True, reason="test"))
    service.publish(candidate.id)

    assert seen["body"]["media_items"][0]["post_ref"] == "drive-processed-1"
    assert seen["body"]["media_items"][0]["media_ref"] == "orig-1", "the original stays named, for the record"


def test_publishing_refuses_when_the_processed_file_never_reached_drive():
    from app.instagram_content import media_pool_service as pool_module
    from app.instagram_content.models import ContentCandidateCreate, ContentDecision, MediaItem
    from app.instagram_content.models import ContentStatus as Status

    pool_module.media_pool_service.reset()
    pool_module.media_pool_service.ingest(MediaPoolIngestRequest(items=[_image_create("orig-2")]))

    def publisher_handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("nothing may reach Instagram without a processed file")

    service = _service_with_mocks(publisher_handler)
    service.reset()
    candidate = service.propose(ContentCandidateCreate(
        media_items=[MediaItem(media_ref="orig-2", media_type="image", aesthetic_score=0.8)],
        caption_draft="Quiet. #trading #discipline #mindset",
    ))
    service.decide(candidate.id, ContentDecision(approved=True, reason="test"))

    with pytest.raises(InstagramContentError, match="no processed file in Drive"):
        service.publish(candidate.id)
    assert service.get(candidate.id).status == Status.post_failed, "loud, and retryable once the upload ran"
