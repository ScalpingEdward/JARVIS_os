from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import httpx

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

DEFAULT_AESTHETIC_CRITERIA = (
    "A high-end, curated account's aesthetic: confident and minimal, warm/consistent "
    "tones, uncluttered composition, deliberate framing. Penalize busy or cluttered "
    "backgrounds, poor lighting, low resolution or visible compression artifacts, "
    "and generic stock-photo composition."
)


class VisionAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionAnalysisConfig:
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("AURON_VISION_MODEL", "claude-sonnet-5"))
    timeout_seconds: float = 30.0
    max_tokens: int = 500
    aesthetic_criteria: str = DEFAULT_AESTHETIC_CRITERIA


@dataclass(frozen=True)
class VisionAnalysisResult:
    theme: str
    tags: list[str]
    aesthetic_score: float
    reasoning: str


class AnthropicVisionAnalyzer:
    """Real image understanding via Claude's vision capability: what's
    actually depicted, and how well *this specific photo* (composition,
    lighting, coherence with the account's look) fits a high-end account --
    not a guessed number.

    AURON still never holds Drive credentials or fetches files itself: the
    caller (n8n, or a script with Drive access) must supply the image
    bytes (base64) or an already-fetchable URL. Fails closed on a missing
    key, a transport/API error, or a response that isn't valid, complete
    JSON with a theme, tags, and a score in range -- never returns a
    guessed score to paper over a bad response.
    """

    def __init__(self, config: VisionAnalysisConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or VisionAnalysisConfig()
        self._client = client

    @staticmethod
    def _image_block(image_base64: str | None, image_media_type: str | None, image_url: str | None) -> dict:
        if image_base64:
            if not image_media_type:
                raise VisionAnalysisError("image_media_type is required when image_base64 is supplied")
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": image_media_type, "data": image_base64},
            }
        if image_url:
            return {"type": "image", "source": {"type": "url", "url": image_url}}
        raise VisionAnalysisError("Either image_base64 (+ image_media_type) or image_url must be supplied")

    def analyze(
        self,
        *,
        image_base64: str | None = None,
        image_media_type: str | None = None,
        image_url: str | None = None,
    ) -> VisionAnalysisResult:
        if not self.config.api_key:
            raise VisionAnalysisError("ANTHROPIC_API_KEY is not set -- AURON cannot analyze an image without it.")

        image_block = self._image_block(image_base64, image_media_type, image_url)

        prompt = (
            "Analyze this photo for a high-end, curated Instagram account.\n\n"
            f"Account aesthetic: {self.config.aesthetic_criteria}\n\n"
            "Respond with ONLY a JSON object, no other text, no markdown fences, in exactly this shape:\n"
            '{"theme": "short-kebab-case-label", "tags": ["tag1", "tag2"], '
            '"aesthetic_score": 0.0, "reasoning": "one sentence"}\n\n'
            "theme: a short, consistent label describing the subject (e.g. 'gold-trading-desk', "
            "'mystic-symbol', 'quote-card', 'portrait-silhouette') -- use the same label for visually "
            "similar photos so they can later be grouped into a carousel together.\n"
            "aesthetic_score: a number from 0.0 to 1.0. Judge THIS photo's composition, lighting, and "
            "coherence with the account aesthetic above -- not just whether the subject is interesting."
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
                    "messages": [{"role": "user", "content": [image_block, {"type": "text", "text": prompt}]}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise VisionAnalysisError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
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
                raise VisionAnalysisError(f"Model response was not valid JSON: {raw[:300]}") from exc

            theme = parsed.get("theme")
            tags = parsed.get("tags")
            aesthetic_score = parsed.get("aesthetic_score")
            reasoning = parsed.get("reasoning", "")

            if not theme or not isinstance(theme, str):
                raise VisionAnalysisError(f"Response missing a valid 'theme': {parsed}")
            if not isinstance(tags, list):
                raise VisionAnalysisError(f"Response missing a valid 'tags' list: {parsed}")
            if not isinstance(aesthetic_score, (int, float)) or not (0 <= aesthetic_score <= 1):
                raise VisionAnalysisError(f"Response missing a valid 'aesthetic_score' in [0,1]: {parsed}")

            return VisionAnalysisResult(
                theme=theme, tags=[str(t) for t in tags], aesthetic_score=float(aesthetic_score), reasoning=str(reasoning)
            )
        except httpx.HTTPError as exc:
            raise VisionAnalysisError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()
