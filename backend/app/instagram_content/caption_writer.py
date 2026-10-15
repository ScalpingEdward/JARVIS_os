from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx

from . import hashtags
from .media_pool_models import MediaPoolItem
from .platform_strategy import platform_strategy_store

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

DEFAULT_BRAND_VOICE = (
    "One person writing, not a brand. Brano, in his own words: a bit crazy, "
    "humble, good-hearted, disciplined, hard on himself, and funny with it. "
    "All of that is allowed to show, and the humour is the part that was "
    "missing most.\n"
    "First person is welcome, so is a single "
    "plain line. Dry, understated, specific. No hype, no emoji spam, no "
    "exclamation-point energy, and never the words 'grind', 'hustle' or "
    "'motivation Monday'.\n"
    "The register is meant to change from post to post, the way a person's "
    "does: an observation, a dry remark, a small admission, half a story, "
    "sometimes just naming where this is. Start from what is actually in the "
    "picture -- the place, the hour, the thing on the table, what just "
    "happened or is about to. Concrete beats poetic.\n"
    "Quiet discipline belongs to this account and may surface now and then: "
    "building without an audience, patience, doing the work unseen. It is "
    "real, and it is rare. Most captions carry no lesson at all. Never two "
    "posts in a row in that register, and never as a formula -- no stacked "
    "'some things are...' lines, no universal truths delivered to the reader. "
    "Said once it sounds like him; said every time it sounds like someone "
    "selling a course.\n"
    "Trading is the author's private discipline, not the subject. Do not write "
    "about markets, charts, trades, sessions, entries, profits, losses, numbers "
    "or results, and never imply money was made or lost. Someone reading the "
    "feed may sense there is a craft behind it; they must never be told what it "
    "earns, and it is never the topic."
)


#: The register that turned every caption into the same sermon. It is not
#: forbidden -- quiet discipline is genuinely part of how Brano writes, and
#: cutting it would cost something real. What is forbidden is using it twice
#: in a row: five captions reached the phone saying a version of "some
#: rewards are quiet enough to need no audience", and he noticed before any
#: check did. A reader meets this voice once and hears a person; four times
#: and hears a course being sold. So it is rationed against history, not
#: banned outright.
_SERMON_PATTERNS = (
    r"\bsome (?:things|rewards|walks|wins|doors|rooms) (?:are|don't|do not)\b",
    r"\bbuil[dt] (?:in|from) (?:silence|the shadows?)\b",
    r"\bin silence\b",
    r"\bstillness\b",
    r"\bno (?:audience|witness|applause)\b",
    r"\bnobody claps\b",
    r"\b(?:doesn't|does not) rush\b",
    r"\bthe (?:quiet|patient) (?:ones?|work)\b",
    r"\blet results speak\b",
)


def _is_sermon(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _SERMON_PATTERNS)


def _sermon_problem(caption: str, recent: list[str] | None) -> str | None:
    """Only a problem when the one before it already spoke that way.

    Judged against the real previous captions rather than a fixed quota:
    that is the difference between a voice Brano owns and a tic. With no
    history to compare against, the caption passes -- a first post is
    allowed to sound like him.
    """
    if not _is_sermon(caption):
        return None
    previous = [c for c in (recent or []) if c and c.strip()]
    if not previous or not _is_sermon(previous[0]):
        return None
    return (
        "the caption before this one already used the quiet-discipline register "
        "(silence, patience, stillness, no audience, 'some things are...'), and two "
        "in a row makes it a tic rather than a voice. Write this one about what is "
        "actually in the picture, with no lesson in it."
    )


def _recent_block(recent: list[str] | None) -> str:
    """The last few captions, so the writer can avoid repeating itself. It
    had no memory at all before: every caption was generated alone from the
    same voice, which is why the same one kept coming back."""
    lines = [c.strip().splitlines()[0] for c in (recent or []) if c and c.strip()][:8]
    if not lines:
        return ""
    joined = "\n".join(f"  - {line[:140]}" for line in lines)
    return (
        "\nThe account's most recent captions opened like this:\n" + joined +
        "\nDo not reuse their opening move, their motif, or their sentence shape. "
        "If what you were about to write resembles one of them, write something else.\n"
    )


class CaptionWriterError(RuntimeError):
    pass


_HASHTAG = re.compile(r"(?<![\w#])#\w+")


def hashtags_in(caption: str) -> list[str]:
    return _HASHTAG.findall(caption)


def count_hashtags(caption: str) -> int:
    return len(hashtags_in(caption))


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

    def _build_prompt(self, theme: str, media_items: list[MediaPoolItem], post_format: str,
                      recent: list[str] | None = None) -> str:
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
            f"- End with exactly {strategy.optimal_hashtag_min}-{strategy.optimal_hashtag_max} hashtags, chosen ONLY "
            f"from this list and copied exactly as written:\n{hashtags.prompt_block()}\n"
            f"  Do not invent hashtags and do not combine words into new ones. Instagram enforces a hard "
            f"{strategy.max_hashtags}-hashtag cap platform-wide as of 2026, and hashtags categorize content "
            f"rather than drive reach -- an invented tag labels the post with something nobody browses.\n"
            f"- No engagement-bait phrases (\"like4like\", \"tag a friend\", \"link in bio now\", \"follow for more\").\n"
            f"- Return ONLY the caption text itself -- no preamble, no explanation, no quotation marks around it.\n"
        )

    def generate(self, theme: str, media_items: list[MediaPoolItem], post_format: str,
                 recent: list[str] | None = None) -> str:
        """Write the caption, and check the two hashtag rules the model
        demonstrably skips: the first real card went out with no hashtags at
        all although the prompt demanded 3-5, the second with five invented
        mood words (#QuietWealth, #StillWaters) nobody browses. Count and
        list membership are both checked here, one corrective retry is made,
        and a caption that still misses fails loudly instead of reaching the
        phone looking finished."""
        if not self.config.api_key:
            raise CaptionWriterError(
                "ANTHROPIC_API_KEY is not set -- AURON cannot generate a caption without it. "
                "Set it in the backend's environment, or supply caption_draft explicitly instead."
            )

        strategy = platform_strategy_store.current()
        low, high = strategy.optimal_hashtag_min, strategy.optimal_hashtag_max
        prompt = self._build_prompt(theme, media_items, post_format, recent)
        caption = self._complete(prompt)
        problem = self._hashtag_problem(caption, low, high) or _sermon_problem(caption, recent)
        if problem is None:
            return caption

        caption = self._complete(prompt + f"\nYour previous answer was rejected: {problem} Fix exactly that.")
        problem = self._hashtag_problem(caption, low, high) or _sermon_problem(caption, recent)
        if problem is None:
            return caption
        raise CaptionWriterError(f"caption rejected after a corrective retry: {problem}")

    @staticmethod
    def _hashtag_problem(caption: str, low: int, high: int) -> str | None:
        """What is wrong with this caption's hashtags, worded so the retry
        can act on it. None when they are fine."""
        tags = hashtags_in(caption)
        unknown = hashtags.unknown_tags(tags)
        if unknown:
            return (
                f"it used {' '.join(unknown)}, which are not on the allowed list. "
                f"Use only hashtags from that list, copied exactly."
            )
        if not low <= len(tags) <= high:
            return f"it contained {len(tags)} hashtags, and the caption must end with {low} to {high}."
        if len({hashtags.normalize(tag) for tag in tags}) != len(tags):
            return "it repeated the same hashtag."
        return None

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
