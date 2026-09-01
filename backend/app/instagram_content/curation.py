from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .media_pool_models import MediaPoolItem
from .models import MediaType
from .platform_strategy import PlatformStrategy, platform_strategy_store

# Convenience re-exports of the default strategy's values, for callers/tests
# that want the current baseline without pulling the whole store. curate()
# itself always reads platform_strategy_store.current() live, so a research-
# driven update (see platform_strategy.py) takes effect without a code change.
_DEFAULTS = PlatformStrategy()
ELITE_SOLO_THRESHOLD = _DEFAULTS.elite_solo_threshold
CAROUSEL_MIN_SIZE = _DEFAULTS.carousel_min_size
CAROUSEL_IDEAL_MAX_SIZE = _DEFAULTS.carousel_ideal_max_size


@dataclass(frozen=True)
class CuratedGroup:
    theme: str
    media_items: list[MediaPoolItem]
    reasoning: str


def curate(pool_items: list[MediaPoolItem], max_groups: int = 10) -> list[CuratedGroup]:
    """Groups unused pool items into post-worthy sets, respecting real
    account-curation logic: standout single images become hero posts,
    videos always stand alone as Reels, same-theme images get batched into
    right-sized carousels (3-6 items) ranked best-first, and no item is
    proposed more than once (across groups within this single call --
    marking items 'used' for real happens one layer up once a group is
    actually turned into a submitted candidate).
    """
    strategy = platform_strategy_store.current()
    unused = [item for item in pool_items if item.available]
    by_theme: dict[str, list[MediaPoolItem]] = defaultdict(list)
    for item in unused:
        by_theme[item.theme].append(item)

    groups: list[CuratedGroup] = []

    for theme, items in by_theme.items():
        items.sort(key=lambda i: i.aesthetic_score, reverse=True)
        remaining: list[MediaPoolItem] = []

        for item in items:
            if item.media_type == MediaType.video:
                groups.append(
                    CuratedGroup(
                        theme=theme,
                        media_items=[item],
                        reasoning=f"Video in theme '{theme}' -- always a standalone Reel, never grouped.",
                    )
                )
            elif item.aesthetic_score >= strategy.elite_solo_threshold:
                groups.append(
                    CuratedGroup(
                        theme=theme,
                        media_items=[item],
                        reasoning=(
                            f"Aesthetic score {item.aesthetic_score:.2f} is above the elite solo bar "
                            f"({strategy.elite_solo_threshold}) -- stands better alone than diluted into a carousel."
                        ),
                    )
                )
            else:
                remaining.append(item)

        batch: list[MediaPoolItem] = []
        for item in remaining:
            batch.append(item)
            if len(batch) == strategy.carousel_ideal_max_size:
                groups.append(
                    CuratedGroup(
                        theme=theme,
                        media_items=list(batch),
                        reasoning=f"{len(batch)} same-theme images ('{theme}') batched into a full carousel.",
                    )
                )
                batch = []
        if len(batch) >= strategy.carousel_min_size:
            groups.append(
                CuratedGroup(
                    theme=theme,
                    media_items=list(batch),
                    reasoning=f"{len(batch)} same-theme images ('{theme}') -- enough for a real carousel set.",
                )
            )
        # A leftover of 1-2 items is deliberately NOT posted: it would read
        # as thin. It stays unused in the pool until more of the same theme
        # arrives, rather than forcing a weak post to use it up.

    groups.sort(key=lambda g: sum(i.aesthetic_score for i in g.media_items) / len(g.media_items), reverse=True)
    return groups[:max_groups]
