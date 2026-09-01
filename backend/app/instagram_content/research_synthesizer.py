from __future__ import annotations

import json

import httpx
from pydantic import BaseModel

from .caption_writer import ANTHROPIC_API_VERSION, ANTHROPIC_MESSAGES_URL
from .platform_strategy import PlatformStrategy
from .web_research import WebResearchResponse


class ResearchSynthesisError(RuntimeError):
    pass


class ResearchSynthesisConfig(BaseModel):
    api_key: str | None = None  # supplied by the caller, same key as CaptionWriterConfig/VisionAnalysisConfig
    model: str = "claude-sonnet-5"
    timeout_seconds: float = 30.0
    max_tokens: int = 800


class PlatformStrategyProposal(BaseModel):
    """A candidate PlatformStrategy update plus why -- never applied by
    itself. A human (or an explicit follow-up call) decides whether to
    call platform_strategy_store.apply() with these values."""

    proposed: PlatformStrategy
    reasoning: str
    sources: list[str]
    raw_answer: str


class ResearchSynthesizer:
    """Turns real Tavily search results into a structured, cited proposal
    for updating PlatformStrategy -- via a real, bounded Anthropic call,
    same discipline as the caption writer and vision analyzer. Fails
    closed on a missing key, transport/API error, or a response that
    isn't valid JSON with every required field.
    """

    def __init__(self, config: ResearchSynthesisConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client

    def synthesize(self, current: PlatformStrategy, research: list[WebResearchResponse]) -> PlatformStrategyProposal:
        if not self.config.api_key:
            raise ResearchSynthesisError("ANTHROPIC_API_KEY is not set -- cannot synthesize a research proposal.")

        research_text = "\n\n".join(
            f"Query: {r.query}\n"
            + (f"Summary: {r.answer}\n" if r.answer else "")
            + "\n".join(f"- [{res.title}]({res.url}): {res.content[:500]}" for res in r.results)
            for r in research
        )

        prompt = (
            "You maintain the platform-rule constants an Instagram content-curation system enforces. "
            "Based ONLY on the research below, propose updated values.\n\n"
            f"Current values: max_hashtags={current.max_hashtags}, "
            f"optimal_hashtag_range=({current.optimal_hashtag_min}-{current.optimal_hashtag_max}), "
            f"carousel_min_size={current.carousel_min_size}, carousel_ideal_max_size={current.carousel_ideal_max_size}\n\n"
            f"Research:\n{research_text}\n\n"
            "Respond with ONLY a JSON object, no other text, no markdown fences:\n"
            '{"max_hashtags": int, "optimal_hashtag_min": int, "optimal_hashtag_max": int, '
            '"carousel_min_size": int, "carousel_ideal_max_size": int, '
            '"reasoning": "2-3 sentences citing what changed and why", "sources": ["url1", "url2"]}\n\n'
            "If the research does not clearly support changing a value, keep it the same as the current value. "
            "Never invent a number the research doesn't support -- cite the specific finding for anything you change."
        )

        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise ResearchSynthesisError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            blocks = data.get("content", [])
            text_parts = [block["text"] for block in blocks if block.get("type") == "text"]
            raw = "".join(text_parts).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ResearchSynthesisError(f"Model response was not valid JSON: {raw[:300]}") from exc

            required = [
                "max_hashtags",
                "optimal_hashtag_min",
                "optimal_hashtag_max",
                "carousel_min_size",
                "carousel_ideal_max_size",
                "reasoning",
                "sources",
            ]
            missing = [key for key in required if key not in parsed]
            if missing:
                raise ResearchSynthesisError(f"Response missing required field(s) {missing}: {parsed}")

            proposed = PlatformStrategy(
                max_hashtags=int(parsed["max_hashtags"]),
                optimal_hashtag_min=int(parsed["optimal_hashtag_min"]),
                optimal_hashtag_max=int(parsed["optimal_hashtag_max"]),
                carousel_min_size=int(parsed["carousel_min_size"]),
                carousel_ideal_max_size=int(parsed["carousel_ideal_max_size"]),
                elite_solo_threshold=current.elite_solo_threshold,
                reason=str(parsed["reasoning"]),
                sources=[str(s) for s in parsed["sources"]],
            )
            return PlatformStrategyProposal(
                proposed=proposed,
                reasoning=str(parsed["reasoning"]),
                sources=[str(s) for s in parsed["sources"]],
                raw_answer=raw,
            )
        except httpx.HTTPError as exc:
            raise ResearchSynthesisError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()
