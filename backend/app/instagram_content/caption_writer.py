from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from .media_pool_models import MediaPoolItem
from .moderation import OPTIMAL_HASHTAG_RANGE

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

DEFAULT_BRAND_VOICE = (
    "Confident, understated, slightly mystical. Short sentences. No hype language, "
    "no emoji spam, no exclamation-point energy. The account's own philosophy is "
    "'build in silence, let results speak.' Captions should feel earned, not performed."
)


class CaptionWriterError(RuntimeError):
    pass


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
            f"- Include exactly {OPTIMAL_HASHTAG_RANGE[0]}-{OPTIMAL_HASHTAG_RANGE[1]} relevant hashtags at the end -- "
            f"Instagram enforces a hard 5-hashtag cap platform-wide as of 2026, and Meta's own guidance is that "
            f"hashtags now categorize content rather than drive reach, so precision matters more than count.\n"
            f"- No engagement-bait phrases (\"like4like\", \"tag a friend\", \"link in bio now\", \"follow for more\").\n"
            f"- Return ONLY the caption text itself -- no preamble, no explanation, no quotation marks around it.\n"
        )

    def generate(self, theme: str, media_items: list[MediaPoolItem], post_format: str) -> str:
        if not self.config.api_key:
            raise CaptionWriterError(
                "ANTHROPIC_API_KEY is not set -- AURON cannot generate a caption without it. "
                "Set it in the backend's environment, or supply caption_draft explicitly instead."
            )

        prompt = self._build_prompt(theme, media_items, post_format)
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
