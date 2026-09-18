from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from .media_pool_models import ContentGapReport, MediaPoolItem, ThemeGap
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
    #: The shoot day this group belongs to, when known -- set whenever
    #: _group_key() resolved to a real captured_at date rather than a
    #: source_group/theme fallback. Drives posting order: one day's groups
    #: must all go out before the next day's, never interleaved.
    day: date | None = None


def _group_key(item: MediaPoolItem) -> str:
    """captured_at's local date takes precedence -- a real shoot day beats
    any label -- then source_group (one Drive folder = one shoot), then
    theme as the last resort when neither is known."""
    if item.captured_at is not None:
        return item.captured_at.date().isoformat()
    return item.source_group or item.theme


def _parse_day(group_key: str) -> date | None:
    """Whether a group_key is a real shoot day or a source_group/theme
    fallback. _group_key() only ever produces an ISO date string in the
    first case, so this is a safe, lossless way to recover it without a
    second parameter threaded through every call site."""
    try:
        return date.fromisoformat(group_key)
    except ValueError:
        return None


def _order_group(items: list[MediaPoolItem]) -> list[MediaPoolItem]:
    """Highest-score item leads as the hook; the rest follow chronologically
    by captured_at (items without a captured_at sort last, in their
    existing relative order) instead of by score."""
    if not items:
        return items
    hook, rest = items[0], items[1:]
    rest.sort(key=lambda i: (i.captured_at is None, i.captured_at or datetime.min))
    return [hook, *rest]


def _carousel_reasoning(batch: list[MediaPoolItem], theme: str, *, full: bool) -> str:
    """Says what is actually in the set. A carousel may now mix stills and
    clips, so describing every one of them as "images" would misreport what
    is going out."""
    videos = sum(1 for i in batch if i.media_type == MediaType.video)
    what = f"{len(batch)} items"
    if videos:
        what += f" ({len(batch) - videos} image, {videos} video)"
    tail = "batched into a full carousel." if full else "-- enough for a real carousel set."
    return f"{what} from '{theme}' {tail}"


def curate(pool_items: list[MediaPoolItem], max_groups: int = 10) -> list[CuratedGroup]:
    """Groups unused pool items into post-worthy sets.

    One quality bar decides everything, and it applies to photos and videos
    alike: at or above the elite solo threshold an item carries a post on
    its own (a video becomes a Reel, a photo a single post); below it, the
    item joins a carousel, where stills and clips may mix freely. Leftovers
    too small for a carousel stay in the pool rather than forcing a thin
    post. No item is proposed twice within one call -- marking items 'used'
    for real happens a layer up, once a group actually becomes a candidate.

    Videos used to bypass the bar entirely and always went solo, so a 0.15
    clip became a Reel while a 0.70 photo was judged too weak to stand
    alone. Reels carry this account's reach; a weak one costs more than a
    weak carousel slide.
    """
    strategy = platform_strategy_store.current()
    unused = [item for item in pool_items if item.available]
    by_theme: dict[str, list[MediaPoolItem]] = defaultdict(list)
    for item in unused:
        by_theme[_group_key(item)].append(item)

    groups: list[CuratedGroup] = []

    for theme, items in by_theme.items():
        day = _parse_day(theme)
        items.sort(key=lambda i: i.aesthetic_score, reverse=True)
        remaining: list[MediaPoolItem] = []

        for item in items:
            # One bar for both media types. A video used to go solo whatever
            # it scored, which meant a 0.15 clip became a Reel while a 0.70
            # photo was considered too weak to stand alone -- 19 of the 31
            # videos in the pool scored under 0.35 and every one of them was
            # being proposed as its own post. Reels carry the account's
            # reach, so a weak one costs more than a weak carousel slide.
            if item.aesthetic_score >= strategy.elite_solo_threshold:
                kind = "Reel" if item.media_type == MediaType.video else "single post"
                groups.append(
                    CuratedGroup(
                        theme=theme,
                        media_items=[item],
                        reasoning=(
                            f"Aesthetic score {item.aesthetic_score:.2f} is above the elite solo bar "
                            f"({strategy.elite_solo_threshold}) -- strong enough to carry a {kind} on its own."
                        ),
                        day=day,
                    )
                )
            else:
                # Below the bar, photos and videos mix in one carousel.
                # Instagram allows it, and a clip that is not strong enough
                # to hold a Reel can still earn its place between stills --
                # it is also what stops a swipe.
                remaining.append(item)

        batch: list[MediaPoolItem] = []
        for item in remaining:
            batch.append(item)
            if len(batch) == strategy.carousel_ideal_max_size:
                groups.append(
                    CuratedGroup(
                        theme=theme,
                        media_items=_order_group(list(batch)),
                        reasoning=_carousel_reasoning(batch, theme, full=True),
                        day=day,
                    )
                )
                batch = []
        if len(batch) >= strategy.carousel_min_size:
            groups.append(
                CuratedGroup(
                    theme=theme,
                    media_items=_order_group(list(batch)),
                    reasoning=_carousel_reasoning(batch, theme, full=False),
                    day=day,
                )
            )
        # A leftover of 1-2 items is deliberately NOT posted: it would read
        # as thin. It stays unused in the pool until more of the same theme
        # arrives, rather than forcing a weak post to use it up.

    # Posting order, not just proposal order: one shoot day's groups must all
    # be exhausted before the next day's begin, oldest day first, so a
    # carousel/reel/single post from the same day always run together
    # instead of interleaving with unrelated days. Groups with no known day
    # (source_group/theme fallback -- today, every Drive video without a
    # captured_at) sort last, since there is nothing to chronologically
    # place them by; score still breaks ties within the same day.
    groups.sort(
        key=lambda g: (
            g.day is None,
            g.day or date.max,
            -(sum(i.aesthetic_score for i in g.media_items) / len(g.media_items)),
        )
    )
    return groups[:max_groups]


DEFAULT_LOW_WATER_MARK = 12


def analyze_gaps(pool_items: list[MediaPoolItem], low_water_mark: int = DEFAULT_LOW_WATER_MARK) -> ContentGapReport:
    """What the pool is missing, in plain terms -- never posts anything,
    never reserves anything, purely a read of the current state.

    Reuses exactly the same theme grouping and thresholds `curate()` uses,
    so a theme reported here as "1 short of a carousel" is the same theme
    `curate()` would silently skip on its next run. Videos and items already
    above the elite solo threshold are never gaps -- they already have a
    path to becoming a post on their own; only same-theme images stuck below
    `carousel_min_size` are.
    """
    strategy = platform_strategy_store.current()
    unused = [item for item in pool_items if item.available]

    by_theme: dict[str, list[MediaPoolItem]] = defaultdict(list)
    for item in unused:
        by_theme[item.theme].append(item)

    gaps: list[ThemeGap] = []
    for theme, items in sorted(by_theme.items()):
        stuck = [
            item for item in items
            if item.media_type == MediaType.image
            and item.aesthetic_score < strategy.elite_solo_threshold
        ]
        # Only the *leftover remainder* is a gap: curate() already turns
        # every full-sized batch into a carousel, so a theme with e.g. 13
        # stuck images has zero gap (12 become carousels, 1 is the leftover).
        remainder = len(stuck) % strategy.carousel_ideal_max_size
        if remainder == 0 or remainder >= strategy.carousel_min_size:
            continue

        needed = strategy.carousel_min_size - remainder
        sample = stuck[-remainder:] if remainder else []
        gaps.append(ThemeGap(
            theme=theme,
            available_count=remainder,
            needed_for_carousel=needed,
            sample_tags=sorted({tag for item in sample for tag in item.tags}),
            sample_media_refs=[item.media_ref for item in sample],
        ))

    return ContentGapReport(
        available_count=len(unused),
        theme_gaps=gaps,
        pool_low=len(unused) <= low_water_mark,
        low_water_mark=low_water_mark,
    )
