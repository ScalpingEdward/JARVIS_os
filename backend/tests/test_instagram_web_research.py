from __future__ import annotations

import json

import httpx
import pytest

from app.instagram_content.platform_strategy import PlatformStrategy, PlatformStrategyStore
from app.instagram_content.research_synthesizer import (
    ResearchSynthesisConfig,
    ResearchSynthesisError,
    ResearchSynthesizer,
)
from app.instagram_content.web_research import (
    TavilyWebResearcher,
    WebResearchConfig,
    WebResearchError,
    WebResearchResponse,
    WebResearchResult,
)


# -- TavilyWebResearcher: real, bounded search call --------------------------


def test_search_fails_closed_without_an_api_key():
    researcher = TavilyWebResearcher(config=WebResearchConfig(api_key=None))
    with pytest.raises(WebResearchError, match="TAVILY_API_KEY is not set"):
        researcher.search("instagram hashtag limit")


def test_search_returns_parsed_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "answer": "Instagram caps hashtags at 5 as of Dec 2025.",
                "results": [
                    {"title": "Hashtag cap 2026", "url": "https://example.com/a", "content": "5-hashtag cap...", "published_date": "2026-04-21"}
                ],
            },
        )

    researcher = TavilyWebResearcher(
        config=WebResearchConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    response = researcher.search("instagram hashtag limit")
    assert response.answer == "Instagram caps hashtags at 5 as of Dec 2025."
    assert response.results[0].title == "Hashtag cap 2026"
    assert response.results[0].url == "https://example.com/a"


def test_search_sends_the_real_api_key_and_query():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"results": [], "answer": None})

    researcher = TavilyWebResearcher(
        config=WebResearchConfig(api_key="sk-tavily-123"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    researcher.search("carousel size 2026")

    assert captured["body"]["api_key"] == "sk-tavily-123"
    assert captured["body"]["query"] == "carousel size 2026"


def test_search_raises_on_api_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    researcher = TavilyWebResearcher(
        config=WebResearchConfig(api_key="bad-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(WebResearchError, match="401"):
        researcher.search("anything")


# -- ResearchSynthesizer: structured, cited proposal from research ----------


def _anthropic_json_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(payload)}]})


def test_synthesize_fails_closed_without_an_api_key():
    synthesizer = ResearchSynthesizer(config=ResearchSynthesisConfig(api_key=None))
    with pytest.raises(ResearchSynthesisError, match="ANTHROPIC_API_KEY is not set"):
        synthesizer.synthesize(PlatformStrategy(), [])


def test_synthesize_returns_a_proposal_never_applies_it():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_json_response(
            {
                "max_hashtags": 5,
                "optimal_hashtag_min": 3,
                "optimal_hashtag_max": 5,
                "carousel_min_size": 3,
                "carousel_ideal_max_size": 10,
                "reasoning": "Confirmed 5-hashtag cap and 7-10 slide sweet spot from current sources.",
                "sources": ["https://example.com/a", "https://example.com/b"],
            }
        )

    synthesizer = ResearchSynthesizer(
        config=ResearchSynthesisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    store = PlatformStrategyStore()
    before = store.current()

    research = [WebResearchResponse(query="q", results=[], answer=None)]
    proposal = synthesizer.synthesize(store.current(), research)

    assert proposal.proposed.max_hashtags == 5
    assert proposal.proposed.carousel_ideal_max_size == 10
    assert len(proposal.sources) == 2
    # Critically: synthesize() never touches the store.
    assert store.current() is before


def test_synthesize_raises_on_missing_required_field():
    def handler(request: httpx.Request) -> httpx.Response:
        return _anthropic_json_response({"max_hashtags": 5, "reasoning": "incomplete"})

    synthesizer = ResearchSynthesizer(
        config=ResearchSynthesisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ResearchSynthesisError, match="missing required field"):
        synthesizer.synthesize(PlatformStrategy(), [])


def test_synthesize_raises_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not json"}]})

    synthesizer = ResearchSynthesizer(
        config=ResearchSynthesisConfig(api_key="test-key"), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ResearchSynthesisError, match="not valid JSON"):
        synthesizer.synthesize(PlatformStrategy(), [])


# -- PlatformStrategyStore: apply is the only way values change -------------


def test_store_starts_with_the_verified_defaults():
    store = PlatformStrategyStore()
    current = store.current()
    assert current.max_hashtags == 5
    assert current.carousel_ideal_max_size == 10


def test_store_only_changes_via_explicit_apply():
    store = PlatformStrategyStore()
    original = store.current()

    new_strategy = PlatformStrategy(
        max_hashtags=7, optimal_hashtag_min=3, optimal_hashtag_max=7, carousel_min_size=3, carousel_ideal_max_size=12,
        reason="Hypothetical future platform change.", sources=["https://example.com/future"],
    )
    applied = store.apply(new_strategy)

    assert applied.max_hashtags == 7
    assert store.current().max_hashtags == 7
    assert original.max_hashtags == 5  # the old snapshot is untouched


# -- API wiring: moderation/curation actually read the live store -----------


def test_moderation_reflects_an_applied_strategy_change():
    from app.instagram_content.media_pool_models import MediaPoolItemCreate
    from app.instagram_content.models import ContentCandidateCreate
    from app.instagram_content.moderation import moderate
    from app.instagram_content.platform_strategy import platform_strategy_store

    original = platform_strategy_store.current()
    try:
        platform_strategy_store.apply(
            PlatformStrategy(max_hashtags=2, optimal_hashtag_min=1, optimal_hashtag_max=2, carousel_min_size=3, carousel_ideal_max_size=10)
        )
        candidate = ContentCandidateCreate(
            media_items=[{"media_ref": "x", "media_type": "image", "aesthetic_score": 0.9}],
            caption_draft="Three tags here. #one #two #three",
        )
        result = moderate(candidate, recent_captions=[])
        assert not result.passed  # 3 hashtags now exceeds the lowered cap of 2
    finally:
        platform_strategy_store.apply(original)
