from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx

from .media_pool_models import MediaPoolItem
from .platform_strategy import platform_strategy_store

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

DEFAULT_BRAND_VOICE = (
    "Confident, understated, slightly mystical. Short sentences. No hype language, "
    "no emoji spam, no exclamation-point energy. The account's own philosophy is "
    "'build in silence, let results speak.' Captions should feel earned, not performed. "
    "Niche: high-performance biohacking, disciplined training, and location-independent "
    "trading, framed through an old-discipline lens (ritual, precision, patience) rather "
    "than generic hustle-culture language. Never use words like 'grind', 'hustle', "
    "'motivation Monday', or stacked exclamation points -- the account earns its energy "
    "through restraint, not volume. The 'mystical' quality is atmosphere, not content: an "
    "occasional mood or moment can carry it (a quiet frame, a loaded word choice), but "
    "never a caption that explains, names, or leans on any specific practice. What that "
    "atmosphere is actually drawn from stays private -- the account gestures at depth, it "
    "never states it."
)


class CaptionWriterError(RuntimeError):
    pass


_HASHTAG = re.compile(r"(?<![\w#])#\w+")


def count_hashtags(caption: str) -> int:
    return len(_HASHTAG.findall(caption))


@dataclass(frozen=True)
class CaptionWriterConfig:
    """API key comes from the environment, never a request payload or a
    default -- there is no safe fallback for a missing credential."""

    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("AURON_CAPTION_MODEL", "claude-sonnet-5"))
    timeout_seconds: float = 30.0
    max_tokens: int = 500
    brand_voice: str = DEFAULT_BRAND_VOICE


class AnthropicCaptionWriter:
    """The one component allowed to generate real caption/hashtag text --
    a real, bounded HTTPS call to Anthropic's own Messages API, not a
    fabrication. Fails closed: no API key, a transport error, an API
    error, or an unparseable response all raise rather than returning a
    guessed caption. Closes the loop that used to require an n8n round
    trip for captioning -- this is the direct replacement for that step,
    not an addition on top of it.
    """

    def __init__(self, config: CaptionWriterConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or CaptionWriterConfig()
        self._client = client

    def _build_prompt(self, theme: str, media_items: list[MediaPoolItem], post_format: str) -> str:
        tag_hint = ", ".join(sorted({t for item in media_items for t in item.tags})) or "none provided"
        strategy = platform_strategy_store.current()
        return (
            f"Write one Instagram caption for a {post_format.replace('_', ' ')} post on a high-end, "
            f"growth-focused account.\n\n"
            f"Brand voice: {self.config.brand_voice}\n\n"
            f"Post theme: {theme}\n"
            f"Media tags observed: {tag_hint}\n"
            f"Number of media items: {len(media_items)}\n\n"
            f"Requirements:\n"
            f"- Opening line must work as a scroll-stopping hook, under 125 characters, "
            f"not a hashtag, not written in all caps.\n"
            f"- Include exactly {strategy.optimal_hashtag_min}-{strategy.optimal_hashtag_max} relevant hashtags at the end -- "
            f"Instagram enforces a hard {strategy.max_hashtags}-hashtag cap platform-wide as of 2026, and Meta's own "
            f"guidance is that hashtags now categorize content rather than drive reach, so precision matters more than count.\n"
            f"- No engagement-bait phrases (\"like4like\", \"tag a friend\", \"link in bio now\", \"follow for more\").\n"
            f"- Return ONLY the caption text itself -- no preamble, no explanation, no quotation marks around it.\n"
        )

    def generate(self, theme: str, media_items: list[MediaPoolItem], post_format: str) -> str:
        """Write the caption, and check the one rule the model demonstrably
        skips: the first real card went out with no hashtags at all although
        the prompt demanded 3-5. The count is checked here, one corrective
        retry is made, and a caption that still misses fails loudly instead
        of reaching the phone looking finished."""
        if not self.config.api_key:
            raise CaptionWriterError(
                "ANTHROPIC_API_KEY is not set -- AURON cannot generate a caption without it. "
                "Set it in the backend's environment, or supply caption_draft explicitly instead."
            )

        strategy = platform_strategy_store.current()
        low, high = strategy.optimal_hashtag_min, strategy.optimal_hashtag_max
        prompt = self._build_prompt(theme, media_items, post_format)
        caption = self._complete(prompt)
        count = count_hashtags(caption)
        if low <= count <= high:
            return caption

        caption = self._complete(
            prompt
            + f"\nYour previous answer contained {count} hashtags. That is not allowed: "
            f"end the caption with between {low} and {high} hashtags, each a real, narrow topic label."
        )
        count = count_hashtags(caption)
        if low <= count <= high:
            return caption
        raise CaptionWriterError(
            f"caption still has {count} hashtags after a corrective retry (need {low}-{high}) -- not sending it"
        )

    def _complete(self, prompt: str) -> str:
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
                raise CaptionWriterError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            blocks = data.get("content", [])
            text_parts = [block["text"] for block in blocks if block.get("type") == "text"]
            caption = "".join(text_parts).strip()
            if not caption:
                raise CaptionWriterError("Anthropic API response did not contain any text content")
            return caption
        except httpx.HTTPError as exc:
            raise CaptionWriterError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()
