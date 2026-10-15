from __future__ import annotations

from .models import MediaItem, MediaType, PostFormat
from .reel_targets import target_max_seconds, target_min_seconds

# Instagram's own real constraints, not house preference:
CAROUSEL_MIN_ITEMS = 2
CAROUSEL_MAX_ITEMS = 10

#: The platform's hard ceiling -- past this Instagram itself refuses the
#: Reel. Not the same thing as the length we aim for, and the two must not
#: be confused again: a single constant named "max" once served as both,
#: so a 46s clip got a trim window calculated against the 30s target during
#: ingest and was then marked "no trim needed" against this 90s ceiling by
#: the edit plan. The analysis was paid for and silently discarded.
#: What we aim for lives in reel_targets.py, is configurable, and is a
#: content-strategy decision; this is a platform fact.
REEL_PLATFORM_MAX_SECONDS = 90.0


def decide_format(media_items: list[MediaItem]) -> tuple[PostFormat, str]:
    """Real, deterministic post-type decision -- not a guess. The three
    branches match Instagram's own structural rules, not a house opinion:
    exactly one video with nothing else can only be a Reel (or a single
    video post, which Instagram now treats as a Reel anyway); exactly one
    image with nothing else is a standalone post; two or more items of any
    mix become a carousel, which is IG's own only way to group multiple
    media into one post.
    """
    if len(media_items) == 1:
        item = media_items[0]
        if item.media_type == MediaType.video:
            reason = (
                f"Single video ({item.duration_seconds:.0f}s) -- Instagram treats standalone video posts as "
                "Reels now, and Reels get materially more organic reach than a static single-image post."
            )
            return PostFormat.reel, reason
        return (
            PostFormat.single_image,
            "Single image, nothing to sequence -- carousels only outperform a single post when there's an "
            "actual story or before/after to walk through; a lone strong image stands on its own.",
        )

    video_count = sum(1 for m in media_items if m.media_type == MediaType.video)
    reason = (
        f"{len(media_items)} items ({video_count} video, {len(media_items) - video_count} image) -- "
        "Instagram carousels are the only native way to group multiple media into one post, and multi-item "
        "posts get a second and third look as people swipe, which the algorithm reads as engagement."
    )
    return PostFormat.carousel, reason


def reel_duration_notes(item: MediaItem) -> list[str]:
    """Warnings about a video's length, measured against the length we aim
    for -- not against the platform ceiling, which is a different question.

    Names the real trim window when one was analyzed, and says plainly that
    nothing will cut the file: no step in this system touches pixels. A
    note that merely said "trimming is recommended" would read like
    something was going to happen.
    """
    if item.media_type != MediaType.video or item.duration_seconds is None:
        return []

    notes: list[str] = []
    if item.duration_seconds > REEL_PLATFORM_MAX_SECONDS:
        notes.append(
            f"{item.duration_seconds:.0f}s is over Instagram's own {REEL_PLATFORM_MAX_SECONDS:.0f}s ceiling -- "
            "the platform will refuse this Reel outright. It has to be cut before it can be posted at all."
        )
    elif item.duration_seconds > target_max_seconds():
        window = ""
        if item.recommended_trim_start_seconds is not None and item.recommended_trim_end_seconds is not None:
            window = (
                f" AURON's analysis of the actual frames picked "
                f"{item.recommended_trim_start_seconds:.1f}s-{item.recommended_trim_end_seconds:.1f}s "
                f"as the strongest segment."
            )
        notes.append(
            f"{item.duration_seconds:.0f}s is longer than the {target_max_seconds():.0f}s this account aims "
            f"for.{window} Nothing here cuts the file -- trim it yourself before posting, or post it as is."
        )
    elif item.duration_seconds < target_min_seconds():
        notes.append(
            f"{item.duration_seconds:.0f}s is under the {target_min_seconds():.0f}s this account aims for -- "
            "short clips tend to read as low-effort and give the algorithm little watch time to work with."
        )
    return notes
