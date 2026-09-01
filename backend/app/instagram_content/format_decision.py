from __future__ import annotations

from .models import MediaItem, MediaType, PostFormat

# Instagram's own real constraints, not house preference:
CAROUSEL_MIN_ITEMS = 2
CAROUSEL_MAX_ITEMS = 10
REEL_MIN_DURATION_SECONDS = 15.0
REEL_MAX_DURATION_SECONDS = 90.0
REEL_IDEAL_DURATION_SECONDS = (15.0, 30.0)  # where Instagram's own algorithm favors completion rate


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
    """Warnings about a video's length relative to what performs well as a
    Reel. Does not decide a trim window -- see edit_plan.py for why."""
    if item.media_type != MediaType.video or item.duration_seconds is None:
        return []
    notes: list[str] = []
    if item.duration_seconds < REEL_MIN_DURATION_SECONDS:
        notes.append(
            f"{item.duration_seconds:.0f}s is under Instagram's practical Reel floor of "
            f"{REEL_MIN_DURATION_SECONDS:.0f}s -- likely to underperform or get treated as a low-effort clip."
        )
    elif item.duration_seconds > REEL_MAX_DURATION_SECONDS:
        notes.append(
            f"{item.duration_seconds:.0f}s exceeds {REEL_MAX_DURATION_SECONDS:.0f}s -- trimming to the "
            f"strongest {REEL_IDEAL_DURATION_SECONDS[0]:.0f}-{REEL_IDEAL_DURATION_SECONDS[1]:.0f}s is recommended "
            "for completion rate, but AURON does not select which segment; that needs a human pick or a real "
            "video-content analysis step, neither of which exists yet."
        )
    return notes
