from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from .caption_writer import ANTHROPIC_API_VERSION, ANTHROPIC_MESSAGES_URL
from .media_pool_models import FrameSample, TrimAnalysisResult


class VideoTrimAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoTrimAnalysisConfig:
    api_key: str | None = None  # supplied by the caller, same key as the other Anthropic-backed components
    model: str = "claude-sonnet-5"
    timeout_seconds: float = 45.0
    max_tokens: int = 500


class AnthropicVideoTrimAnalyzer:
    """Picks a real highlight window for an over-length Reel from actual
    sampled frames -- not an invented timestamp. Sends every supplied frame
    to Claude in one call, each labeled with its real timestamp, and asks
    for the strongest contiguous window drawn from those exact sample
    points. Validates the response lands within the sampled range and
    respects min/max ordering before trusting it -- a response outside the
    actual sampled timestamps is treated as a bad response, not clamped
    into something that looks plausible.
    """

    def __init__(self, config: VideoTrimAnalysisConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or VideoTrimAnalysisConfig()
        self._client = client

    def analyze(
        self, frames: list[FrameSample], target_min_seconds: float, target_max_seconds: float
    ) -> TrimAnalysisResult:
        if not self.config.api_key:
            raise VideoTrimAnalysisError("ANTHROPIC_API_KEY is not set -- AURON cannot analyze video frames without it.")
        if len(frames) < 3:
            raise VideoTrimAnalysisError("At least 3 sampled frames are required to pick a trim window.")

        sorted_frames = sorted(frames, key=lambda f: f.timestamp_seconds)
        min_ts, max_ts = sorted_frames[0].timestamp_seconds, sorted_frames[-1].timestamp_seconds

        content: list[dict] = []
        for frame in sorted_frames:
            if frame.image_base64:
                if not frame.image_media_type:
                    raise VideoTrimAnalysisError("image_media_type is required when image_base64 is supplied")
                content.append(
                    {"type": "image", "source": {"type": "base64", "media_type": frame.image_media_type, "data": frame.image_base64}}
                )
            elif frame.image_url:
                content.append({"type": "image", "source": {"type": "url", "url": frame.image_url}})
            else:
                raise VideoTrimAnalysisError(f"Frame at {frame.timestamp_seconds}s has neither image_base64 nor image_url")
            content.append({"type": "text", "text": f"^ frame at {frame.timestamp_seconds:.1f}s"})

        prompt = (
            f"These are {len(sorted_frames)} sampled frames from a video, in order, each labeled with its real "
            f"timestamp (spanning {min_ts:.1f}s to {max_ts:.1f}s). Pick the strongest contiguous window for an "
            f"Instagram Reel, ideally {target_min_seconds:.0f}-{target_max_seconds:.0f}s long.\n\n"
            f"Your recommended_start_seconds and recommended_end_seconds MUST both be timestamps that fall "
            f"within {min_ts:.1f}-{max_ts:.1f}s (the range actually sampled) -- do not guess a time outside "
            f"what you were shown.\n\n"
            'Respond with ONLY a JSON object, no other text, no markdown fences:\n'
            '{"recommended_start_seconds": 0.0, "recommended_end_seconds": 0.0, "reasoning": "one sentence"}'
        )
        content.append({"type": "text", "text": prompt})

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
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise VideoTrimAnalysisError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            blocks = data.get("content", [])
            text_parts = [b["text"] for b in blocks if b.get("type") == "text"]
            raw = "".join(text_parts).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise VideoTrimAnalysisError(f"Model response was not valid JSON: {raw[:300]}") from exc

            start = parsed.get("recommended_start_seconds")
            end = parsed.get("recommended_end_seconds")
            reasoning = parsed.get("reasoning", "")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise VideoTrimAnalysisError(f"Response missing valid start/end timestamps: {parsed}")
            start, end = float(start), float(end)

            if not (min_ts <= start <= max_ts) or not (min_ts <= end <= max_ts):
                raise VideoTrimAnalysisError(
                    f"Model returned a window ({start}-{end}s) outside the sampled range "
                    f"({min_ts}-{max_ts}s) -- treating as an invalid response, not clamping it."
                )
            if end <= start:
                raise VideoTrimAnalysisError(f"Model returned end ({end}s) <= start ({start}s).")

            return TrimAnalysisResult(recommended_start_seconds=start, recommended_end_seconds=end, reasoning=str(reasoning))
        except httpx.HTTPError as exc:
            raise VideoTrimAnalysisError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()
