from __future__ import annotations

from .format_decision import REEL_IDEAL_DURATION_SECONDS, REEL_MAX_DURATION_SECONDS, reel_duration_notes
from .models import EditInstruction, MediaItem, MediaType, PostFormat

# One consistent grade across the account is the actual "high-end look" --
# a different filter per post reads as random, not curated. Named, not a
# magic string, so n8n's real editing step (LUT/preset in whatever tool
# actually processes the file) has one stable identifier to key off.
BRAND_COLOR_GRADE_PRESET = "auron-warm-mystic-v1"

ASPECT_RATIO_FEED = "4:5"  # tallest ratio Instagram's feed still displays at full size -- more screen real estate
ASPECT_RATIO_REEL = "9:16"


def build_edit_plan(media_items: list[MediaItem], post_format: PostFormat) -> list[EditInstruction]:
    """One instruction per media item: target aspect ratio and the account's
    one consistent color-grade preset, always. Trim recommendations for
    over-length video, but never an invented trim window -- see
    reel_duration_notes for why that stays a human/real-analysis job."""
    instructions: list[EditInstruction] = []
    for item in media_items:
        if item.media_type == MediaType.video:
            notes = reel_duration_notes(item)
            needs_trim = item.duration_seconds is not None and item.duration_seconds > REEL_MAX_DURATION_SECONDS
            instructions.append(
                EditInstruction(
                    media_ref=item.media_ref,
                    target_aspect_ratio=ASPECT_RATIO_REEL,
                    color_grade_preset=BRAND_COLOR_GRADE_PRESET,
                    target_duration_seconds=REEL_IDEAL_DURATION_SECONDS,
                    trim_needed=needs_trim,
                    notes="; ".join(notes) if notes else "Duration is within range; no trim needed.",
                )
            )
        else:
            instructions.append(
                EditInstruction(
                    media_ref=item.media_ref,
                    target_aspect_ratio=ASPECT_RATIO_FEED,
                    color_grade_preset=BRAND_COLOR_GRADE_PRESET,
                    notes=(
                        "Crop to 4:5 and apply the account's standard grade for feed consistency."
                        if post_format != PostFormat.reel
                        else "Single-image Reel cover frame; grade applied, aspect ratio matches the video."
                    ),
                )
            )
    return instructions
