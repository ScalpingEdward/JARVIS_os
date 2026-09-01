from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PlatformStrategy(BaseModel):
    """The numbers moderation.py and curation.py actually enforce. Kept as
    one small, explicit, versioned object -- not scattered module
    constants -- so a research-driven update can replace the whole set
    atomically, with a reason and sources attached, instead of quietly
    drifting one constant at a time."""

    max_hashtags: int = 5
    optimal_hashtag_min: int = 3
    optimal_hashtag_max: int = 5
    carousel_min_size: int = 3
    carousel_ideal_max_size: int = 10
    elite_solo_threshold: float = 0.85
    updated_at: datetime = Field(default_factory=lambda: datetime(2026, 8, 31, tzinfo=timezone.utc))
    reason: str = (
        "Initial values verified via web search 2026-08-31: Instagram enforces a hard 5-hashtag "
        "cap platform-wide (Dec 2025), and 2026 engagement data shows a 7-10 slide carousel sweet spot."
    )
    sources: list[str] = Field(default_factory=list)


class PlatformStrategyStore:
    """Holds exactly one current PlatformStrategy. Updates only ever happen
    through `apply()`, called explicitly after a human reviews a proposal
    -- `research_synthesizer.py`'s refresh step never calls this itself."""

    def __init__(self) -> None:
        self._current = PlatformStrategy()

    def current(self) -> PlatformStrategy:
        return self._current

    def apply(self, strategy: PlatformStrategy) -> PlatformStrategy:
        self._current = strategy
        return self._current

    def reset(self) -> None:
        self._current = PlatformStrategy()


platform_strategy_store = PlatformStrategyStore()
