from __future__ import annotations

import re

from .models import ContentCandidateCreate

# Deliberately explicit and editable in one place, not scattered constants --
# this is the account's brand/compliance policy, not a technical detail.
MAX_CAPTION_LENGTH = 2200  # Instagram's own hard limit
# Instagram enforces a HARD 5-hashtag cap platform-wide since December 2025
# (applies to posts, Reels, and comments combined -- not a "best practice",
# a publish-time restriction). Verified via web search 2026-08-31; re-verify
# if this code is revisited far in the future, platform rules change.
MAX_HASHTAGS = 5
OPTIMAL_HASHTAG_RANGE = (3, 5)  # Meta's own official recommendation as of 2026; Instagram's head has stated
# hashtags no longer drive reach directly, only content categorization -- precision over volume.
MIN_AESTHETIC_SCORE_HARD = 0.35  # below this: not the account's aesthetic, auto-reject
MIN_AESTHETIC_SCORE_SOFT = 0.6  # below this but above the hard floor: let a human decide, but flag it

BANNED_PHRASES = (
    "follow4follow",
    "f4f",
    "like4like",
    "l4l",
    "sub4sub",
    "click the link in bio now",
    "dm for promo",
    "guaranteed followers",
)

_HASHTAG_RE = re.compile(r"#\w+")


class ModerationResult:
    def __init__(self, violations: list[str] | None = None, warnings: list[str] | None = None) -> None:
        self.violations = violations or []
        self.warnings = warnings or []

    @property
    def passed(self) -> bool:
        return not self.violations


def moderate(candidate: ContentCandidateCreate, recent_captions: list[str]) -> ModerationResult:
    """Runs explicit, deterministic policy checks before a candidate ever
    reaches a human for approval. Violations auto-reject (never shown to
    the human as pending); warnings still go to human review, just flagged.

    This exists so review time goes to real judgment calls (does this fit
    the aesthetic, is the caption's voice right) instead of catching
    spam-pattern captions or duplicate posts by hand every time.
    """
    violations: list[str] = []
    warnings: list[str] = []

    caption = candidate.caption_draft.strip()
    if not caption:
        violations.append("Caption is empty.")
    if len(caption) > MAX_CAPTION_LENGTH:
        violations.append(f"Caption exceeds Instagram's {MAX_CAPTION_LENGTH}-character limit.")

    hashtags = _HASHTAG_RE.findall(caption)
    if len(hashtags) > MAX_HASHTAGS:
        violations.append(
            f"{len(hashtags)} hashtags exceeds Instagram's platform-enforced {MAX_HASHTAGS}-hashtag cap "
            "(publish-time restriction since Dec 2025, not just a style guideline)."
        )
    elif len(hashtags) == 0:
        warnings.append(
            "No hashtags at all -- even though hashtags no longer drive reach directly, they still help "
            "Instagram categorize the post correctly; a missed classification signal."
        )
    elif len(hashtags) < OPTIMAL_HASHTAG_RANGE[0]:
        warnings.append(
            f"Only {len(hashtags)} hashtag(s); Meta's own current guidance is "
            f"{OPTIMAL_HASHTAG_RANGE[0]}-{OPTIMAL_HASHTAG_RANGE[1]} for the clearest categorization signal."
        )

    lowered = caption.lower()
    hit_phrases = [phrase for phrase in BANNED_PHRASES if phrase in lowered]
    if hit_phrases:
        violations.append(f"Caption contains spam-pattern phrase(s): {', '.join(hit_phrases)}.")

    scores = [item.aesthetic_score for item in candidate.media_items]
    average_score = sum(scores) / len(scores)
    weakest_score = min(scores)
    if average_score < MIN_AESTHETIC_SCORE_HARD:
        violations.append(
            f"Average aesthetic score {average_score:.2f} is below the account's minimum bar "
            f"({MIN_AESTHETIC_SCORE_HARD})."
        )
    elif average_score < MIN_AESTHETIC_SCORE_SOFT:
        warnings.append(
            f"Average aesthetic score {average_score:.2f} is below the usual bar "
            f"({MIN_AESTHETIC_SCORE_SOFT}) -- borderline fit for the account."
        )
    if len(scores) > 1 and weakest_score < MIN_AESTHETIC_SCORE_HARD:
        warnings.append(
            f"At least one media item scores {weakest_score:.2f}, below the account's minimum bar -- "
            "consider dropping it from the carousel even if the average is fine."
        )

    if caption in recent_captions:
        violations.append("This exact caption was already proposed recently (near-duplicate content).")

    return ModerationResult(violations=violations, warnings=warnings)
